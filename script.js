document.addEventListener("DOMContentLoaded", () => {
    // ---- Elements -----------------------------------------------------
    const renderForm = document.getElementById("renderForm");
    const submitBtn = document.getElementById("submitBtn");
    const loader = document.getElementById("loader");
    const statusText = document.getElementById("statusText");
    const resultBox = document.getElementById("resultBox");
    const errorBox = document.getElementById("errorBox");
    const errorText = document.getElementById("errorText");
    const downloadBtn = document.getElementById("downloadBtn");

    const settingsToggle = document.getElementById("settingsToggle");
    const settingsClose = document.getElementById("settingsClose");
    const settingsPanel = document.getElementById("settingsPanel");
    const geminiKeyInput = document.getElementById("geminiKeyInput");
    const hfKeyInput = document.getElementById("hfKeyInput");
    const geminiStatus = document.getElementById("geminiStatus");
    const hfStatus = document.getElementById("hfStatus");
    const saveSettingsBtn = document.getElementById("saveSettingsBtn");
    const settingsMsg = document.getElementById("settingsMsg");

    let pollTimer = null;

    // ---- Settings panel -------------------------------------------------
    function setStatusBadge(el, isSet, maskedValue) {
        if (isSet) {
            el.textContent = "✓ saved";
            el.className = "text-xs text-emerald-400";
            el.title = maskedValue || "";
        } else {
            el.textContent = "not set";
            el.className = "text-xs text-slate-500";
            el.title = "";
        }
    }

    async function loadSettingsStatus() {
        try {
            const res = await fetch("/api/settings");
            const data = await res.json();
            setStatusBadge(geminiStatus, data.gemini_api_key_set, data.gemini_api_key_masked);
            setStatusBadge(hfStatus, data.huggingface_api_token_set, data.huggingface_api_token_masked);
            if (data.gemini_api_key_set) geminiKeyInput.placeholder = data.gemini_api_key_masked;
            if (data.huggingface_api_token_set) hfKeyInput.placeholder = data.huggingface_api_token_masked;
        } catch (err) {
            geminiStatus.textContent = "?";
            hfStatus.textContent = "?";
        }
    }

    settingsToggle.addEventListener("click", () => {
        settingsPanel.classList.toggle("hidden");
        if (!settingsPanel.classList.contains("hidden")) loadSettingsStatus();
    });
    settingsClose.addEventListener("click", () => settingsPanel.classList.add("hidden"));

    saveSettingsBtn.addEventListener("click", async () => {
        const gemini_api_key = geminiKeyInput.value.trim();
        const huggingface_api_token = hfKeyInput.value.trim();

        if (!gemini_api_key && !huggingface_api_token) {
            settingsMsg.textContent = "Paste at least one key first.";
            settingsMsg.className = "text-xs text-amber-400";
            return;
        }

        saveSettingsBtn.disabled = true;
        try {
            const res = await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ gemini_api_key, huggingface_api_token })
            });
            const data = await res.json();
            if (!res.ok || !data.success) throw new Error(data.error || "Save failed.");

            settingsMsg.textContent = "Saved.";
            settingsMsg.className = "text-xs text-emerald-400";
            geminiKeyInput.value = "";
            hfKeyInput.value = "";
            await loadSettingsStatus();
        } catch (err) {
            settingsMsg.textContent = "Error: " + err.message;
            settingsMsg.className = "text-xs text-red-400";
        } finally {
            saveSettingsBtn.disabled = false;
        }
    });

    loadSettingsStatus();

    // ---- Video generation (async job + polling) --------------------------
    function resetResultStates() {
        resultBox.classList.add("hidden");
        errorBox.classList.add("hidden");
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    function pollJob(jobId) {
        pollTimer = setInterval(async () => {
            try {
                const res = await fetch(`/api/job-status/${jobId}`);
                const data = await res.json();

                if (!res.ok || !data.success) {
                    throw new Error(data.error || "Lost track of this job.");
                }

                if (data.stage) statusText.innerText = data.stage;

                if (data.status === "done") {
                    stopPolling();
                    loader.classList.add("hidden");
                    resultBox.classList.remove("hidden");
                    downloadBtn.href = data.video_url;
                    submitBtn.disabled = false;
                    submitBtn.classList.remove("opacity-50", "cursor-not-allowed");
                } else if (data.status === "error") {
                    stopPolling();
                    loader.classList.add("hidden");
                    errorBox.classList.remove("hidden");
                    errorText.innerText = data.error || "Something went wrong.";
                    submitBtn.disabled = false;
                    submitBtn.classList.remove("opacity-50", "cursor-not-allowed");
                }
            } catch (err) {
                stopPolling();
                loader.classList.add("hidden");
                errorBox.classList.remove("hidden");
                errorText.innerText = err.message;
                submitBtn.disabled = false;
                submitBtn.classList.remove("opacity-50", "cursor-not-allowed");
            }
        }, 3000);
    }

    renderForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const topic = document.getElementById("topic").value.trim();
        const aspectRatio = document.getElementById("aspect_ratio").value;
        const language = document.getElementById("language").value;

        if (!topic) {
            alert("Please provide an Islamic story topic.");
            return;
        }

        submitBtn.disabled = true;
        submitBtn.classList.add("opacity-50", "cursor-not-allowed");
        loader.classList.remove("hidden");
        resetResultStates();
        statusText.innerText = "Queued...";

        try {
            const response = await fetch("/api/generate-video", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                // NOTE: the backend expects snake_case keys (aspect_ratio),
                // so we map the camelCase local variable explicitly here.
                body: JSON.stringify({ topic, aspect_ratio: aspectRatio, language })
            });

            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || "Failed to start the job.");
            }

            pollJob(data.job_id);

        } catch (err) {
            loader.classList.add("hidden");
            errorBox.classList.remove("hidden");
            errorText.innerText = err.message;
            submitBtn.disabled = false;
            submitBtn.classList.remove("opacity-50", "cursor-not-allowed");
        }
    });
});
