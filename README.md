# LoopGenerator

A web-based sequencer and loop generator that uses Tone.js to create and play musical loops (especially focused on Baroque style patterns).

## Running the Application

To run the local server, execute:
- `run.bat` (Windows)
- Or manually: `python main.py`

Then open your browser at `http://localhost:8000/catalog.html`

## Local Audio Samples (Tone.js Salamander Grand Piano)

To ensure the application works completely offline, avoids Tone.js `buffer not loaded` timeout errors, and has high-quality sound across the entire frequency spectrum without extreme pitch-shifting, this project uses local `.mp3` samples for the Piano synthesizer.

**Important:** The piano samples must be located in the `static/audio/salamander/` directory.

The project requires the following 30 notes to cover the full piano range (A0 to C8):
`A0.mp3`, `C1.mp3`, `Ds1.mp3`, `Fs1.mp3`, `A1.mp3`, `C2.mp3`, `Ds2.mp3`, `Fs2.mp3`, `A2.mp3`, `C3.mp3`, `Ds3.mp3`, `Fs3.mp3`, `A3.mp3`, `C4.mp3`, `Ds4.mp3`, `Fs4.mp3`, `A4.mp3`, `C5.mp3`, `Ds5.mp3`, `Fs5.mp3`, `A5.mp3`, `C6.mp3`, `Ds6.mp3`, `Fs6.mp3`, `A6.mp3`, `C7.mp3`, `Ds7.mp3`, `Fs7.mp3`, `A7.mp3`, `C8.mp3`.

If you are cloning this repository for the first time and these files are missing (or ignored by Git), you can download them directly from the Tone.js audio repository:
`https://tonejs.github.io/audio/salamander/{note_name}.mp3` 
(e.g., `https://tonejs.github.io/audio/salamander/C4.mp3`).

Total size of all 30 samples is approximately **1.9 MB**.
