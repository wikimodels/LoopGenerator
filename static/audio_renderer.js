// audio_renderer.js
// Shared audio rendering logic for all pages.
//
// РЕНДЕР ЭКСПОРТА — ОФЛАЙНОВЫЙ (Tone.Offline), не в реальном времени.
// Старый путь (Tone.Recorder + MediaRecorder поверх живого контекста) был
// источником битых файлов: сворачивание таба душило setTimeout'ы, запись
// обрезалась или оставалась пустой, webm не содержал duration. Офлайн-рендер
// детерминирован: быстрее реального времени, не зависит от видимости вкладки,
// а результат проверяется объективно (длительность + не-тишина) с ретраем.

// Global guard: Tone.js can throw RangeError("Value must be within [0, Infinity]")
// asynchronously from WebAudio scheduler — uncatchable via try/catch.
window.addEventListener('unhandledrejection', (e) => {
    if (e.reason && (e.reason instanceof RangeError || e.reason.name === 'RangeError')) {
        e.preventDefault();
        window.dispatchEvent(new Event('audio_glitch'));
    }
});

window.addEventListener('error', (e) => {
    if (e.error && (e.error instanceof RangeError || e.error.name === 'RangeError')) {
        e.preventDefault();
        window.dispatchEvent(new Event('audio_glitch'));
    }
});


let silentSynths = {};
let isSharedAudioInitialized = false;
let exportCancelled = false;

const SALAMANDER_URLS = { "A0": "A0.mp3", "C1": "C1.mp3", "D#1": "Ds1.mp3", "F#1": "Fs1.mp3", "A1": "A1.mp3", "C2": "C2.mp3", "D#2": "Ds2.mp3", "F#2": "Fs2.mp3", "A2": "A2.mp3", "C3": "C3.mp3", "D#3": "Ds3.mp3", "F#3": "Fs3.mp3", "A3": "A3.mp3", "C4": "C4.mp3", "D#4": "Ds4.mp3", "F#4": "Fs4.mp3", "A4": "A4.mp3", "C5": "C5.mp3", "D#5": "Ds5.mp3", "F#5": "Fs5.mp3", "A5": "A5.mp3", "C6": "C6.mp3", "D#6": "Ds6.mp3", "F#6": "Fs6.mp3", "A6": "A6.mp3", "C7": "C7.mp3", "D#7": "Ds7.mp3", "F#7": "Fs7.mp3", "A7": "A7.mp3", "C8": "C8.mp3" };

const MIME = {
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.webm': 'audio/webm'
};

async function initSilentSynths() {
    if (isSharedAudioInitialized) return;
    if (Tone.context.state !== 'running') {
        await Tone.start();
    }

    // Живые инструменты больше не нужны для экспорта (рендер офлайновый),
    // но инициализация прогревает кэш сэмплов фортепиано (LRU-кэш Tone),
    // чтобы офлайновый Sampler собирался мгновенно и без сети.
    const pianoPromise = new Promise(resolve => {
        const sampler = new Tone.Sampler({
            urls: SALAMANDER_URLS,
            release: 1,
            baseUrl: "/audio/salamander/",
            onload: () => resolve(sampler)
        }).toDestination();
    });

    silentSynths = {
        piano: await pianoPromise
    };

    isSharedAudioInitialized = true;
}

function exportSingleLoopSilent(loopData, overrideBpm) {
    return (async () => {
        const maxAttempts = 3;
        let lastErr = null;

        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            if (exportCancelled) return null;
            try {
                const buffer = await renderLoopOffline(loopData, overrideBpm);

                // ── Объективная верификация результата ──
                const expectedSec = loopExpectedDuration(loopData, overrideBpm);
                if (!buffer || !buffer.duration) throw new Error('empty render');
                if (buffer.duration < expectedSec * 0.9) {
                    throw new Error(`render too short: ${buffer.duration.toFixed(2)}s < ${expectedSec.toFixed(2)}s`);
                }
                const peak = bufferPeak(buffer);
                if ((loopData.notes || []).length > 0 && peak < 0.0001) {
                    throw new Error(`silent render (peak=${peak.toExponential(1)})`);
                }

                return await encodeRenderedAudio(buffer);
            } catch (e) {
                lastErr = e;
                console.warn(`[Export] attempt ${attempt}/${maxAttempts} failed: ${e.message}`);
                await new Promise(r => setTimeout(r, 200));
            }
        }
        console.error(`[Export] giving up after ${maxAttempts} attempts: ${lastErr && lastErr.message}`);
        return null;
    })();
}

// ─── Offline rendering core ──────────────────────────────────────────────────

function loopTiming(loopData, overrideBpm) {
    const bpm = overrideBpm || loopData.bpm || 120;
    // Each step = one "8n" (eighth note): steps * 30 / bpm seconds.
    const durationSec = loopData.steps * 30 / bpm;
    const MIN_DURATION_SEC = 7;
    const loopCount = durationSec < MIN_DURATION_SEC
        ? Math.ceil(MIN_DURATION_SEC / durationSec)
        : 1;
    return { bpm, durationSec, loopCount };
}

function loopExpectedDuration(loopData, overrideBpm) {
    const { durationSec, loopCount } = loopTiming(loopData, overrideBpm);
    return durationSec * loopCount + RENDER_TAIL_SEC;
}

const RENDER_TAIL_SEC = 1.0; // хвост на release сэмплов после последнего шага

function bufferPeak(buffer) {
    let peak = 0;
    for (let ch = 0; ch < buffer.numberOfChannels; ch++) {
        const data = buffer.getChannelData(ch);
        for (let i = 0; i < data.length; i++) {
            const v = Math.abs(data[i]);
            if (v > peak) peak = v;
        }
    }
    return peak;
}

async function renderLoopOffline(loopData, overrideBpm) {
    await initSilentSynths(); // прогрев кэша сэмплов

    try {
        const loadTimeout = new Promise((_, rej) =>
            setTimeout(() => rej(new Error('load timeout')), 10000)
        );
        await Promise.race([Tone.loaded(), loadTimeout]);
    } catch (e) {
        console.warn('renderLoopOffline: sample load timeout, rendering anyway', e);
    }

    const { bpm, loopCount } = loopTiming(loopData, overrideBpm);
    const totalDurationSec = loopTiming(loopData, overrideBpm).durationSec * loopCount + RENDER_TAIL_SEC;

    const instrument = loopData.instrument;
    const swing = loopData.swing || 0.0;

    const stepNotes = {};
    (loopData.notes || []).forEach(n => {
        if (!stepNotes[n.step]) stepNotes[n.step] = [];
        stepNotes[n.step].push(n);
    });
    const stepsArray = Array.from({ length: loopData.steps }, (_, i) => i);

    return await Tone.Offline(async (offlineCtx) => {
        // Все инструменты создаются ВНУТРИ офлайн-контекста.
        const limiter = new Tone.Limiter(-1).toDestination();
        const bus = new Tone.Volume(0).connect(limiter);

        const synth = new Tone.PolySynth(Tone.Synth).connect(bus);
        synth.maxPolyphony = 64;
        const amSynth = new Tone.PolySynth(Tone.AMSynth).connect(bus);
        amSynth.maxPolyphony = 64;
        const fmSynth = new Tone.PolySynth(Tone.FMSynth).connect(bus);
        fmSynth.maxPolyphony = 64;

        // Сэмплы уже в LRU-кэше Tone (прогреты initSilentSynths), поэтому
        // Sampler собирается из кэша и onload срабатывает почти мгновенно.
        const piano = await new Promise((resolve) => {
            const s = new Tone.Sampler({
                urls: SALAMANDER_URLS,
                release: 1,
                baseUrl: "/audio/salamander/",
                onload: () => resolve(s)
            }).connect(bus);
            if (s.loaded) resolve(s); // защита от гонки onload
        });

        const drums = createOfflineDrumKit(bus);

        let currentSynth = { synth, amSynth, fmSynth, piano, drums }[instrument] || piano;

        // ВАЖНО: Tone 14.8 держит свой Transport у каждого контекста.
        // Глобальный Tone.Transport может указывать на живой контекст —
        // управляем именно офлайн-транспортом, иначе рендер будет пустым.
        const transport = (offlineCtx && offlineCtx.transport)
            ? offlineCtx.transport
            : (typeof Tone.getTransport === 'function' ? Tone.getTransport() : Tone.Transport);

        transport.bpm.value = bpm;
        transport.swing = swing;
        transport.swingSubdivision = "8n";

        const tempSequence = new Tone.Sequence((time, step) => {
            if (!stepNotes[step]) return;
            stepNotes[step].forEach((n, idx) => {
                const chance = n.chance ?? 1.0;
                const velocity = n.velocity ?? 1.0;
                if (Math.random() <= chance) {
                    const t = time + (idx * 0.0001); // микро-оффсет для аккордов
                    try {
                        currentSynth.triggerAttackRelease(n.note, n.duration || "8n", t, velocity);
                    } catch (_) {}
                }
            });
        }, stepsArray, "8n").start(0.001);

        tempSequence.loop = loopCount > 1 ? loopCount - 1 : false;

        // Офлайн-транспорт не стартует сам — запускаем явно от начала рендера.
        transport.start(0);
    }, totalDurationSec);
}

/** Стационарный драм-кит для офлайна: без setTimeout/dispose (в офлайне
 *  реального времени нет) — синтезаторы живут до конца рендера. */
function createOfflineDrumKit(outputNode) {
    const kick = new Tone.MembraneSynth({
        pitchDecay: 0.05,
        octaves: 4,
        oscillator: { type: 'sine' },
        envelope: { attack: 0.001, decay: 0.4, sustain: 0.01, release: 1.4 }
    }).connect(outputNode);
    const snare = new Tone.NoiseSynth({
        noise: { type: 'white' },
        envelope: { attack: 0.001, decay: 0.2, sustain: 0, release: 0.2 }
    }).connect(outputNode);
    const hh = new Tone.MetalSynth({
        frequency: 200,
        envelope: { attack: 0.001, decay: 0.1, release: 0.01 },
        harmonicity: 5.1,
        modulationIndex: 32,
        resonance: 4000,
        octaves: 1.5
    }).connect(outputNode);
    hh.volume.value = -12;

    return {
        triggerAttackRelease: (note, duration, time, velocity) => {
            if (note.includes('C1')) kick.triggerAttackRelease("C1", "8n", time, velocity);
            else if (note.includes('D1')) snare.triggerAttackRelease("16n", time, velocity);
            else if (note.includes('F#1')) hh.triggerAttackRelease("32n", time, velocity);
        }
    };
}

// ─── Output encoding (MP3 через lamejs, фолбэк — WAV) ───────────────────────

/** Целевое расширение экспорта. Определяется один раз: mp3, если lamejs
 *  загружен, иначе wav. Все вызывающие страницы обязаны использовать
 *  EXPORT_EXT для имён файлов. */
let _exportExt = null;
function exportExt() {
    if (_exportExt === null) {
        _exportExt = (typeof lamejs !== 'undefined') ? 'mp3' : 'wav';
    }
    return _exportExt;
}

const MP3_KBPS = 192;

function floatToInt16(f32) {
    const out = new Int16Array(f32.length);
    for (let i = 0; i < f32.length; i++) {
        const s = Math.max(-1, Math.min(1, f32[i]));
        out[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return out;
}

async function encodeRenderedAudio(buffer) {
    if (typeof lamejs !== 'undefined') {
        try {
            return audioBufferToMp3(buffer);
        } catch (e) {
            console.warn('[Export] MP3 encode failed, falling back to WAV:', e.message);
        }
    }
    return new Blob([audioBufferToWav(buffer)], { type: 'audio/wav' });
}

/** AudioBuffer -> MP3 Blob (lamejs). Энкодер принимает блоки по кратные
 *  1152 сэмплов; последний вызов — flush(). */
function audioBufferToMp3(buffer) {
    const numCh = Math.min(2, buffer.numberOfChannels);
    const sampleRate = buffer.sampleRate;
    const encoder = new lamejs.Mp3Encoder(numCh, sampleRate, MP3_KBPS);

    const channels = [];
    for (let ch = 0; ch < numCh; ch++) channels.push(floatToInt16(buffer.getChannelData(ch)));

    const blockSize = 1152;
    const data = [];
    for (let i = 0; i < channels[0].length; i += blockSize) {
        const left = channels[0].subarray(i, i + blockSize);
        const right = numCh > 1 ? channels[1].subarray(i, i + blockSize) : null;
        const chunk = numCh > 1 ? encoder.encodeBuffer(left, right) : encoder.encodeBuffer(left);
        if (chunk.length > 0) data.push(new Uint8Array(chunk));
    }
    const end = encoder.flush();
    if (end.length > 0) data.push(new Uint8Array(end));

    return new Blob(data, { type: 'audio/mpeg' });
}

// ─── WAV encoding (фолбэк) ───────────────────────────────────────────────────

/** AudioBuffer -> 16-bit PCM WAV ArrayBuffer. */
function audioBufferToWav(buffer, bitDepth = 16) {
    const numCh = buffer.numberOfChannels;
    const sampleRate = buffer.sampleRate;
    const format = bitDepth === 32 ? 3 : 1; // 1 = PCM, 3 = float
    const bytesPerSample = bitDepth / 8;
    const blockAlign = numCh * bytesPerSample;

    const data = [];
    for (let ch = 0; ch < numCh; ch++) data.push(buffer.getChannelData(ch));
    const len = data[0].length;

    const dataSize = len * blockAlign;
    const ab = new ArrayBuffer(44 + dataSize);
    const view = new DataView(ab);

    const writeStr = (off, s) => {
        for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
    };

    writeStr(0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeStr(8, 'WAVE');
    writeStr(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, format, true);
    view.setUint16(22, numCh, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitDepth, true);
    writeStr(36, 'data');
    view.setUint32(40, dataSize, true);

    let off = 44;
    for (let i = 0; i < len; i++) {
        for (let ch = 0; ch < numCh; ch++) {
            let s = Math.max(-1, Math.min(1, data[ch][i]));
            if (bitDepth === 16) {
                view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
                off += 2;
            } else {
                view.setFloat32(off, s, true);
                off += 4;
            }
        }
    }
    return ab;
}
