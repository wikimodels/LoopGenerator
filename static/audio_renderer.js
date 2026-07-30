// audio_renderer.js
// Shared audio rendering logic for all pages

// Global guard: Tone.js can throw RangeError("Value must be within [0, Infinity]")
// asynchronously from WebAudio scheduler — uncatchable via try/catch.
// We swallow ONLY this specific error so it never breaks the export flow.
window.addEventListener('unhandledrejection', (e) => {
    if (e.reason && (e.reason instanceof RangeError || e.reason.name === 'RangeError')) {
        e.preventDefault(); // suppress console error + don't crash
        window.dispatchEvent(new Event('audio_glitch'));
    }
});

// Also catch synchronous WebAudio errors bubbling up to window
window.addEventListener('error', (e) => {
    if (e.error && (e.error instanceof RangeError || e.error.name === 'RangeError')) {
        e.preventDefault();
        window.dispatchEvent(new Event('audio_glitch'));
    }
});


let silentSynths = {};
let recorder = null;
let exportLimiter = null;
let exportRecorderNode = null;
let isSharedAudioInitialized = false;
let exportCancelled = false;

async function initSilentSynths() {
    if (isSharedAudioInitialized) return;
    if (Tone.context.state !== 'running') {
        await Tone.start();
    }

    const silentGain = new Tone.Gain(0).toDestination();
    exportLimiter = new Tone.Limiter(-1).connect(silentGain);
    exportRecorderNode = new Tone.Volume(0).connect(exportLimiter);

    const synth = new Tone.PolySynth(Tone.Synth).connect(exportRecorderNode);
    synth.maxPolyphony = 64;
    
    const amSynth = new Tone.PolySynth(Tone.AMSynth).connect(exportRecorderNode);
    amSynth.maxPolyphony = 64;
    
    const fmSynth = new Tone.PolySynth(Tone.FMSynth).connect(exportRecorderNode);
    fmSynth.maxPolyphony = 64;

    const pianoPromise = new Promise(resolve => {
        const sampler = new Tone.Sampler({
            urls: { "A0": "A0.mp3", "C1": "C1.mp3", "D#1": "Ds1.mp3", "F#1": "Fs1.mp3", "A1": "A1.mp3", "C2": "C2.mp3", "D#2": "Ds2.mp3", "F#2": "Fs2.mp3", "A2": "A2.mp3", "C3": "C3.mp3", "D#3": "Ds3.mp3", "F#3": "Fs3.mp3", "A3": "A3.mp3", "C4": "C4.mp3", "D#4": "Ds4.mp3", "F#4": "Fs4.mp3", "A4": "A4.mp3", "C5": "C5.mp3", "D#5": "Ds5.mp3", "F#5": "Fs5.mp3", "A5": "A5.mp3", "C6": "C6.mp3", "D#6": "Ds6.mp3", "F#6": "Fs6.mp3", "A6": "A6.mp3", "C7": "C7.mp3", "D#7": "Ds7.mp3", "F#7": "Fs7.mp3", "A7": "A7.mp3", "C8": "C8.mp3" },
            release: 1,
            baseUrl: "/audio/salamander/",
            onload: () => resolve(sampler)
        }).connect(exportRecorderNode);
    });

    silentSynths = {
        synth: synth,
        amSynth: amSynth,
        fmSynth: fmSynth,
        piano: await pianoPromise,
        drums: createDrumKit(exportRecorderNode)
    };

    isSharedAudioInitialized = true;
}

function createDrumKit(outputNode) {
    const dest = outputNode || Tone.getDestination();
    const mk = (s) => { s.connect(dest); return s; };

    return {
        triggerAttackRelease: (note, duration, time, velocity) => {
            if (note.includes('C1')) {
                const kick = mk(new Tone.MembraneSynth({
                    pitchDecay: 0.05,
                    octaves: 4,
                    oscillator: { type: 'sine' },
                    envelope: { attack: 0.001, decay: 0.4, sustain: 0.01, release: 1.4 }
                }));
                kick.triggerAttackRelease("C1", "8n", time, velocity);
                setTimeout(() => kick.dispose(), 2000);
            } else if (note.includes('D1')) {
                const snare = mk(new Tone.NoiseSynth({
                    noise: { type: 'white' },
                    envelope: { attack: 0.001, decay: 0.2, sustain: 0, release: 0.2 }
                }));
                snare.triggerAttackRelease("16n", time, velocity);
                setTimeout(() => snare.dispose(), 2000);
            } else if (note.includes('F#1')) {
                const hh = mk(new Tone.MetalSynth({
                    frequency: 200,
                    envelope: { attack: 0.001, decay: 0.1, release: 0.01 },
                    harmonicity: 5.1,
                    modulationIndex: 32,
                    resonance: 4000,
                    octaves: 1.5
                }));
                hh.volume.value = -12;
                hh.triggerAttackRelease("32n", time, velocity);
                setTimeout(() => hh.dispose(), 2000);
            }
        }
    };
}

function exportSingleLoopSilent(loopData, overrideBpm) {
    return new Promise((resolve) => {
        let attempt = 0;
        const maxAttempts = 3;

        async function tryExport() {
            attempt++;
            let glitchDetected = false;
            const onGlitch = () => { glitchDetected = true; };
            window.addEventListener('audio_glitch', onGlitch);

            await initSilentSynths();
        
        const currentSynth = silentSynths[loopData.instrument] || silentSynths.piano;
        const bpm = overrideBpm || loopData.bpm || 120;

        // 1. Wait for all audio samples to load (piano Sampler loads from CDN).
        try {
            const loadTimeout = new Promise((_, rej) =>
                setTimeout(() => rej(new Error('load timeout')), 10000)
            );
            await Promise.race([Tone.loaded(), loadTimeout]);
        } catch (e) {
            console.warn('exportSingleLoopSilent: sample load timeout, exporting anyway', e);
        }

        if (exportCancelled) { resolve(null); return; }

        if (Tone.context.state !== 'running') {
            await Tone.context.resume();
        }

        // 2. Fresh Tone.Recorder for every track.
        if (recorder) {
            try { 
                if (recorder.state === "started") {
                    await recorder.stop(); 
                }
            } catch (_) {}
            try { recorder.dispose(); } catch (_) {}
        }
        recorder = new Tone.Recorder();
        exportRecorderNode.disconnect();
        exportRecorderNode.connect(exportLimiter); // Keep connected to hardware silently
        exportRecorderNode.connect(recorder);

        // 3. Reset Transport completely before each track.
        Tone.Transport.stop();
        Tone.Transport.cancel();
        // Tone.Transport.position = 0; // REMOVED: setting position to 0 directly causes Tone.js internal RangeErrors (-2.27e-12)
        Tone.Transport.bpm.value = bpm;
        Tone.Transport.swing = loopData.swing || 0.0;
        Tone.Transport.swingSubdivision = "8n";

        const stepsArray = Array.from({length: loopData.steps}, (_, i) => i);
        const stepNotes = {};
        loopData.notes.forEach(n => {
            if (!stepNotes[n.step]) stepNotes[n.step] = [];
            stepNotes[n.step].push(n);
        });

        // Each step = one "8n" (eighth note). durationSec = steps * 30 / bpm
        const durationSec = loopData.steps * 30 / bpm;

        const tempSequence = new Tone.Sequence((time, step) => {
            // Hard clamp: never schedule behind audioContext.currentTime.
            // Tone.js internally converts transport time → AudioContext time; floating-point
            // rounding can produce tiny negatives (-2e-12) that WebAudio rejects asynchronously
            // (uncatchable with try/catch). Pinning to currentTime+0.005 eliminates the issue.
            const minSafe = Tone.context.currentTime + 0.005;
            const safeTime = Math.max(minSafe, time);
            
            if (stepNotes[step]) {
                stepNotes[step].forEach((n, idx) => {
                    const chance   = n.chance   !== undefined ? n.chance   : 1.0;
                    const velocity = n.velocity !== undefined ? n.velocity : 1.0;
                    if (Math.random() <= chance) {
                        // Micro-offset prevents PolySynth floating point crash on exact same time chords
                        const t = Math.max(0, safeTime + (idx * 0.0001));

                        // Fallback if piano buffer failed to load
                        if (currentSynth === silentSynths.piano && !silentSynths.piano.loaded) {
                            currentSynth = silentSynths.synth;
                        }

                        const trigger = (at) => {
                            if (currentSynth === silentSynths.drums) {
                                currentSynth.triggerAttackRelease(n.note, n.duration || "8n", at, velocity);
                            } else if (currentSynth.triggerAttackRelease) {
                                currentSynth.triggerAttackRelease(n.note, n.duration || "8n", at, velocity);
                            } else if (currentSynth.triggerAttack) {
                                currentSynth.triggerAttack(n.note, at);
                            }
                        };

                        try {
                            trigger(t);
                        } catch (e) {
                            if (e instanceof RangeError || (e && e.name === 'RangeError')) {
                                try { trigger(Tone.context.currentTime + 0.005); } catch (_) {}
                            } else {
                                console.warn("Tone.js warning: suppressed error:", e);
                            }
                        }
                    }
                });
            }

        }, stepsArray, "8n").start(0);

        // If loop is shorter than 7s, repeat it until total >= 7s
        const MIN_DURATION_SEC = 7;
        const loopCount = durationSec < MIN_DURATION_SEC
            ? Math.ceil(MIN_DURATION_SEC / durationSec)
            : 1;
        const totalDurationSec = durationSec * loopCount;

        if (loopCount > 1) {
            tempSequence.loop = loopCount - 1;  // Tone.js loop=N means "repeat N times" (plays N+1 total)
        } else {
            tempSequence.loop = false;
        }

        // 4. Start recorder, then wait 150 ms pre-roll so MediaRecorder is
        //    guaranteed in 'recording' state before audio starts flowing.
        recorder.start();
        await new Promise(res => setTimeout(res, 150));
        
        if (exportCancelled) {
            try { await recorder.stop(); } catch (_) {}
            tempSequence.dispose();
            window.removeEventListener('audio_glitch', onGlitch);
            resolve(null);
            return;
        }
        
        // start(time) explicitly defines start position without modifying global .position directly
        Tone.Transport.start(Tone.context.currentTime + 0.1);

        // Allow cancel to abort mid-render
        let exportTimeoutId;
        const cancelWatcher = setInterval(() => {
            if (exportCancelled) {
                clearInterval(cancelWatcher);
                clearTimeout(exportTimeoutId);
                Tone.Transport.stop();
                tempSequence.stop();
                tempSequence.dispose();
                window.removeEventListener('audio_glitch', onGlitch);
                if (recorder && recorder.state === "started") {
                    recorder.stop().then(() => resolve(null)).catch(() => resolve(null));
                } else {
                    resolve(null);
                }
            }
        }, 250);

        exportTimeoutId = setTimeout(async () => {
            clearInterval(cancelWatcher);
            Tone.Transport.stop();
            tempSequence.stop();
            tempSequence.dispose();

            // Hard safety: if recorder.stop() hangs, bail after 8 s
            let recording = null;
            if (recorder && recorder.state === "started") {
                const hardTimeout = new Promise(res => setTimeout(() => res(null), 8000));
                recording = await Promise.race([recorder.stop(), hardTimeout]);
            }

            window.removeEventListener('audio_glitch', onGlitch);

            if (glitchDetected && attempt < maxAttempts) {
                console.warn(`[Export] Audio glitch detected on attempt ${attempt}, regenerating track...`);
                // Give WebAudio a moment to clean up before retrying
                setTimeout(tryExport, 100);
            } else {
                if (glitchDetected) {
                    console.error(`[Export] Track still glitched after ${maxAttempts} attempts. Giving up.`);
                }
                resolve(recording);
            }
        }, (totalDurationSec + 1.5) * 1000);
        
        } // end of tryExport()
        
        tryExport();
    });
}
