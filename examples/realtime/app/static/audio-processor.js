class AudioProcessor extends AudioWorkletProcessor {
    process(inputs) {
        const inputChannel = inputs[0];
        if (inputChannel && inputChannel[0]) {
            this.port.postMessage(inputChannel[0]);
        }
        return true;
    }
}

registerProcessor('audio-processor', AudioProcessor);
