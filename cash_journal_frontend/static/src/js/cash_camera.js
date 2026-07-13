(function () {
    function setVisible(element, visible) {
        if (!element) {
            return;
        }
        element.classList.toggle("d-none", !visible);
    }

    function setStatus(statusElement, message) {
        if (!statusElement) {
            return;
        }
        statusElement.textContent = message || "";
        setVisible(statusElement, Boolean(message));
    }

    function stopStream(stream) {
        if (!stream) {
            return;
        }
        stream.getTracks().forEach((track) => track.stop());
    }

    function dataUrlToFile(dataUrl) {
        const parts = dataUrl.split(",");
        const metadata = parts[0].match(/:(.*?);/);
        const mimetype = metadata ? metadata[1] : "image/jpeg";
        const binary = atob(parts[1]);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) {
            bytes[index] = binary.charCodeAt(index);
        }
        return new File([bytes], "receipt-camera.jpg", {type: mimetype});
    }

    function assignFile(inputElement, dataUrl) {
        if (!inputElement || !window.DataTransfer || !window.File) {
            return;
        }
        const transfer = new DataTransfer();
        transfer.items.add(dataUrlToFile(dataUrl));
        inputElement.files = transfer.files;
    }

    function showModal(modalElement) {
        if (window.Modal) {
            window.Modal.getOrCreateInstance(modalElement).show();
            return;
        }
        modalElement.classList.add("show");
        modalElement.style.display = "block";
        modalElement.removeAttribute("aria-hidden");
    }

    function hideModal(modalElement) {
        if (window.Modal) {
            window.Modal.getOrCreateInstance(modalElement).hide();
            return;
        }
        modalElement.classList.remove("show");
        modalElement.style.display = "none";
        modalElement.setAttribute("aria-hidden", "true");
    }

    function initializeCamera(rootElement) {
        if (rootElement.dataset.cashCameraReady) {
            return;
        }
        rootElement.dataset.cashCameraReady = "1";

        const openButton = rootElement.querySelector("[data-cash-camera-open]");
        const modalElement = rootElement.querySelector("[data-cash-camera-modal]");
        const fileInput = rootElement.querySelector("[name='receipt_image']");
        const dataInput = rootElement.querySelector("[data-cash-camera-data]");
        const thumbnail = rootElement.querySelector("[data-cash-camera-thumbnail]");
        if (!openButton || !modalElement || !fileInput || !dataInput) {
            return;
        }

        const captureButton = modalElement.querySelector("[data-cash-camera-capture]");
        const useButton = modalElement.querySelector("[data-cash-camera-use]");
        const video = modalElement.querySelector("[data-cash-camera-video]");
        const canvas = modalElement.querySelector("[data-cash-camera-canvas]");
        const preview = modalElement.querySelector("[data-cash-camera-preview]");
        const statusElement = modalElement.querySelector("[data-cash-camera-status]");
        const cameraFileInput = modalElement.querySelector(
            "[data-cash-camera-file-input]"
        );
        if (!captureButton || !useButton || !video || !canvas || !preview) {
            return;
        }

        let stream = null;
        let capturedDataUrl = "";

        function resetCapture() {
            capturedDataUrl = "";
            useButton.disabled = true;
            setVisible(preview, false);
            setVisible(video, true);
            if (cameraFileInput) {
                cameraFileInput.value = "";
            }
        }

        function waitForVideoFrame(videoElement, timeoutMs) {
            return new Promise((resolve, reject) => {
                if (videoElement.videoWidth > 0 && videoElement.videoHeight > 0) {
                    resolve();
                    return;
                }
                let settled = false;
                const onLoaded = () => {
                    if (
                        !settled &&
                        videoElement.videoWidth > 0 &&
                        videoElement.videoHeight > 0
                    ) {
                        settled = true;
                        videoElement.removeEventListener("loadedmetadata", onLoaded);
                        resolve();
                    }
                };
                setTimeout(() => {
                    if (settled) {
                        return;
                    }
                    settled = true;
                    videoElement.removeEventListener("loadedmetadata", onLoaded);
                    reject(new Error("No video frame received"));
                }, timeoutMs);
                videoElement.addEventListener("loadedmetadata", onLoaded);
            });
        }

        async function startCamera() {
            resetCapture();
            setStatus(statusElement, "");
            if (!window.isSecureContext) {
                setStatus(
                    statusElement,
                    "Camera access needs HTTPS or localhost. Use image upload instead."
                );
                captureButton.disabled = true;
                return;
            }
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                setStatus(
                    statusElement,
                    "Camera access is not supported by this browser. Use image upload."
                );
                captureButton.disabled = true;
                return;
            }
            try {
                setStatus(statusElement, "Opening camera...");
                stream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        facingMode: {ideal: "environment"},
                        width: {ideal: 1280},
                        height: {ideal: 960},
                    },
                    audio: false,
                });
                video.srcObject = stream;
                await video.play();
                try {
                    await waitForVideoFrame(video, 4000);
                } catch {
                    throw Object.assign(new Error("No camera frames"), {
                        name: "NoVideoFrame",
                    });
                }
                captureButton.disabled = false;
                setStatus(statusElement, "");
            } catch (error) {
                stopStream(stream);
                stream = null;
                video.srcObject = null;
                const message =
                    error && error.name === "NoVideoFrame"
                        ? "The camera did not provide a video feed. Use image upload instead."
                        : `Camera access was blocked or no camera is available${
                              error && error.name ? ` (${error.name})` : ""
                          }. Use image upload instead.`;
                setStatus(statusElement, message);
                captureButton.disabled = true;
            }
        }

        function stopCamera() {
            stopStream(stream);
            stream = null;
            video.srcObject = null;
            captureButton.disabled = true;
        }

        function applyPreview(dataUrl, message) {
            capturedDataUrl = dataUrl;
            preview.src = capturedDataUrl;
            setVisible(preview, true);
            setVisible(video, false);
            useButton.disabled = false;
            setStatus(statusElement, message);
        }

        openButton.addEventListener("click", () => showModal(modalElement));
        modalElement.addEventListener("shown.bs.modal", startCamera);
        modalElement.addEventListener("hidden.bs.modal", stopCamera);

        captureButton.addEventListener("click", () => {
            const width = video.videoWidth || 1280;
            const height = video.videoHeight || 960;
            canvas.width = width;
            canvas.height = height;
            canvas.getContext("2d").drawImage(video, 0, 0, width, height);
            applyPreview(canvas.toDataURL("image/jpeg", 0.9), "Photo captured.");
        });

        if (cameraFileInput) {
            cameraFileInput.addEventListener("change", () => {
                const file = cameraFileInput.files && cameraFileInput.files[0];
                if (!file) {
                    return;
                }
                const reader = new FileReader();
                reader.onload = () => applyPreview(reader.result, "Image selected.");
                reader.readAsDataURL(file);
            });
        }

        useButton.addEventListener("click", () => {
            if (!capturedDataUrl) {
                return;
            }
            dataInput.value = capturedDataUrl;
            assignFile(fileInput, capturedDataUrl);
            if (thumbnail) {
                thumbnail.src = capturedDataUrl;
                setVisible(thumbnail, true);
            }
            hideModal(modalElement);
        });

        fileInput.addEventListener("change", () => {
            dataInput.value = "";
            setVisible(thumbnail, false);
        });
    }

    function initializeAllCameras() {
        document.querySelectorAll("[data-cash-camera]").forEach(initializeCamera);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeAllCameras);
    } else {
        initializeAllCameras();
    }
})();
