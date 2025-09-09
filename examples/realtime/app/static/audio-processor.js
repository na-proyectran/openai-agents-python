class AudioProcessor extends AudioWorkletProcessor {
    process(inputs) {
        const input = inputs[0];
        if (input && input[0]) {
            const samples = input[0];
            const int16Buffer = new Int16Array(samples.length);
            for (let i = 0; i < samples.length; i++) {
                int16Buffer[i] = Math.max(-32768, Math.min(32767, samples[i] * 32768));
            }
            this.port.postMessage(int16Buffer);
        }
        return true;
    }
}

registerProcessor('audio-processor', AudioProcessor);
