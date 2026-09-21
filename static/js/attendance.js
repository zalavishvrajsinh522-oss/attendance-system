const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const statusMsg = document.getElementById("statusMsg");
const locStatus = document.getElementById("locStatus");

async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
    } catch (err) {
        if (statusMsg) {
            statusMsg.textContent = "Camera access denied. Please allow camera permissions.";
            statusMsg.className = "status-msg error";
        }
    }
}

function getLocationIfNeeded() {
    if (typeof GEOFENCE_ENABLED === "undefined" || !GEOFENCE_ENABLED) {
        return Promise.resolve(null);
    }
    if (!navigator.geolocation) {
        if (locStatus) {
            locStatus.textContent = "Geolocation not supported by this browser.";
            locStatus.className = "status-msg error";
        }
        return Promise.resolve(null);
    }
    if (locStatus) {
        locStatus.textContent = "Getting your location...";
        locStatus.className = "status-msg";
    }
    return new Promise((resolve) => {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                if (locStatus) {
                    locStatus.textContent = "Location captured.";
                    locStatus.className = "status-msg ok";
                }
                resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude });
            },
            (err) => {
                if (locStatus) {
                    locStatus.textContent = "Could not get location: " + err.message;
                    locStatus.className = "status-msg error";
                }
                resolve(null);
            },
            { enableHighAccuracy: true, timeout: 8000 }
        );
    });
}

function captureFrame() {
    const ctx = canvas.getContext("2d");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.9);
}

async function markLecturePresent(subjectId, btn) {
    btn.disabled = true;
    btn.textContent = "Checking...";
    statusMsg.textContent = "Getting location...";
    statusMsg.className = "status-msg";

    const pos = await getLocationIfNeeded();
    if (typeof GEOFENCE_ENABLED !== "undefined" && GEOFENCE_ENABLED && !pos) {
        statusMsg.textContent = "Location is required to mark attendance.";
        statusMsg.className = "status-msg error";
        btn.disabled = false;
        btn.textContent = "Mark Present";
        return;
    }

    statusMsg.textContent = "Scanning face...";
    const image = captureFrame();

    try {
        const res = await fetch("/api/recognize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                image,
                subject_id: subjectId,
                lat: pos ? pos.lat : null,
                lng: pos ? pos.lng : null,
            }),
        });
        const data = await res.json();
        statusMsg.textContent = data.message;
        statusMsg.className = "status-msg " + (data.ok ? "ok" : "error");

        if (data.ok) {
            btn.outerHTML = '<span class="badge badge-present">Marked</span>';
        } else {
            btn.disabled = false;
            btn.textContent = "Mark Present";
        }
    } catch (err) {
        statusMsg.textContent = "Error contacting server.";
        statusMsg.className = "status-msg error";
        btn.disabled = false;
        btn.textContent = "Mark Present";
    }
}

document.querySelectorAll(".mark-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        const subjectId = btn.getAttribute("data-subject-id");
        markLecturePresent(subjectId, btn);
    });
});

if (video) {
    startCamera();
    if (typeof GEOFENCE_ENABLED !== "undefined" && GEOFENCE_ENABLED) getLocationIfNeeded();
}
