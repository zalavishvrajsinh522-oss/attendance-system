const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const statusMsg = document.getElementById("statusMsg");
const startBtn = document.getElementById("startBtn");
const finishBtn = document.getElementById("finishBtn");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");

let capturedCount = 0;
let capturing = false;
let intervalId = null;

async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
    } catch (err) {
        statusMsg.textContent = "Camera access denied. Please allow camera permissions.";
        statusMsg.className = "status-msg error";
    }
}

function captureFrame() {
    const ctx = canvas.getContext("2d");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.9);
}

async function sendSample() {
    const image = captureFrame();
    try {
        const res = await fetch("/api/save_sample", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ label: LABEL, image }),
        });
        const data = await res.json();
        if (data.ok) {
            capturedCount = data.count;
            const pct = Math.min(100, (capturedCount / MIN_SAMPLES) * 100);
            progressFill.style.width = pct + "%";
            progressText.textContent = `${capturedCount} / ${MIN_SAMPLES} samples captured`;
            statusMsg.textContent = "Good, keep going...";
            statusMsg.className = "status-msg ok";
            if (capturedCount >= MIN_SAMPLES) {
                stopCapturing();
                statusMsg.textContent = "Enough samples! Click 'Finish & Train Model'.";
                finishBtn.style.display = "inline-block";
            }
        } else {
            statusMsg.textContent = data.message || "No face detected, adjust position.";
            statusMsg.className = "status-msg error";
        }
    } catch (err) {
        statusMsg.textContent = "Error contacting server.";
        statusMsg.className = "status-msg error";
    }
}

function stopCapturing() {
    capturing = false;
    if (intervalId) clearInterval(intervalId);
    startBtn.textContent = "Start Capturing";
}

startBtn.addEventListener("click", () => {
    if (capturing) { stopCapturing(); return; }
    capturing = true;
    startBtn.textContent = "Capturing... (click to stop)";
    intervalId = setInterval(sendSample, 500);
});

finishBtn.addEventListener("click", async () => {
    finishBtn.disabled = true;
    finishBtn.textContent = "Training model...";
    try {
        const res = await fetch("/api/finish_registration", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ label: LABEL }),
        });
        const data = await res.json();
        if (data.ok) {
            statusMsg.textContent = "Model trained! Redirecting...";
            statusMsg.className = "status-msg ok";
            setTimeout(() => { window.location.href = "/dashboard"; }, 1500);
        } else {
            statusMsg.textContent = data.message || "Training failed.";
            statusMsg.className = "status-msg error";
            finishBtn.disabled = false;
            finishBtn.textContent = "Finish & Train Model";
        }
    } catch (err) {
        statusMsg.textContent = "Error contacting server.";
        statusMsg.className = "status-msg error";
        finishBtn.disabled = false;
    }
});

startCamera();
