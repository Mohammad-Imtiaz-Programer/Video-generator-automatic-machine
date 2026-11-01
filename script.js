document.addEventListener("DOMContentLoaded", () => {
    const renderForm = document.getElementById("renderForm");
    const submitBtn = document.getElementById("submitBtn");
    const loader = document.getElementById("loader");
    const statusText = document.getElementById("statusText");
    const resultBox = document.getElementById("resultBox");
    const downloadBtn = document.getElementById("downloadBtn");

    // ===================== API কী সেটিংস (localStorage) =====================
    // কী গুলো কখনো কোড/ফাইলে লেখা হয় না — শুধু এই ব্রাউজারে সেভ থাকে এবং
    // ভিডিও বানানোর রিকোয়েস্টের সাথে সরাসরি সার্ভারে পাঠানো হয়।
    const LS_GEMINI_KEY = "halal_cartoon_gemini_api_key";
    const LS_HF_KEY = "halal_cartoon_hf_token";

    const settingsPanel = document.getElementById("settingsPanel");
    const settingsToggle = document.getElementById("settingsToggle");
    const settingsClose = document.getElementById("settingsClose");
    const geminiKeyInput = document.getElementById("geminiKeyInput");
    const hfKeyInput = document.getElementById("hfKeyInput");
    const saveKeysBtn = document.getElementById("saveKeysBtn");
    const clearKeysBtn = document.getElementById("clearKeysBtn");
    const keySaveStatus = document.getElementById("keySaveStatus");

    function safeGetItem(key) {
        try {
            return localStorage.getItem(key) || "";
        } catch (e) {
            return "";
        }
    }

    function safeSetItem(key, value) {
        try {
            localStorage.setItem(key, value);
            return true;
        } catch (e) {
            return false;
        }
    }

    function safeRemoveItem(key) {
        try {
            localStorage.removeItem(key);
        } catch (e) {
            /* private-browsing mode etc. — ignore */
        }
    }

    // পেজ লোড হওয়ার সময় আগের সেভ করা কী থাকলে বক্সে বসিয়ে দাও
    geminiKeyInput.value = safeGetItem(LS_GEMINI_KEY);
    hfKeyInput.value = safeGetItem(LS_HF_KEY);
    if (geminiKeyInput.value || hfKeyInput.value) {
        keySaveStatus.innerText = "✓ আগের সেভ করা কী পাওয়া গেছে";
    }

    settingsToggle.addEventListener("click", () => {
        settingsPanel.classList.toggle("hidden");
    });
    settingsClose.addEventListener("click", () => {
        settingsPanel.classList.add("hidden");
    });

    // চোখ আইকনে ক্লিক করলে কী দেখা/লুকানো টগল হবে
    document.querySelectorAll(".toggle-key-visibility").forEach((btn) => {
        btn.addEventListener("click", () => {
            const targetInput = document.getElementById(btn.dataset.toggleFor);
            const icon = btn.querySelector("i");
            if (targetInput.type === "password") {
                targetInput.type = "text";
                icon.classList.replace("fa-eye", "fa-eye-slash");
            } else {
                targetInput.type = "password";
                icon.classList.replace("fa-eye-slash", "fa-eye");
            }
        });
    });

    saveKeysBtn.addEventListener("click", () => {
        const geminiOk = safeSetItem(LS_GEMINI_KEY, geminiKeyInput.value.trim());
        const hfOk = safeSetItem(LS_HF_KEY, hfKeyInput.value.trim());
        keySaveStatus.innerText = (geminiOk && hfOk)
            ? "✓ এই ব্রাউজারে সেভ হয়েছে"
            : "⚠ সেভ করা যায়নি (প্রাইভেট ব্রাউজিং মোড?)";
    });

    clearKeysBtn.addEventListener("click", () => {
        safeRemoveItem(LS_GEMINI_KEY);
        safeRemoveItem(LS_HF_KEY);
        geminiKeyInput.value = "";
        hfKeyInput.value = "";
        keySaveStatus.innerText = "মুছে ফেলা হয়েছে";
    });

    // ===================== ভিডিও জেনারেট ফর্ম =====================
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
        resultBox.classList.add("hidden");
        statusText.innerText = "Generating script, voiceovers, and visuals...";

        // সেভ করা (বা এই মুহূর্তে বক্সে লেখা) কী গুলো রিকোয়েস্টের সাথে পাঠানো হয়।
        // খালি রাখলে সার্ভার .env-এর ডিফল্ট কী (যদি থাকে) ব্যবহার করবে।
        const geminiApiKey = (geminiKeyInput.value || safeGetItem(LS_GEMINI_KEY)).trim();
        const huggingfaceApiToken = (hfKeyInput.value || safeGetItem(LS_HF_KEY)).trim();

        try {
            const response = await fetch("/api/generate-video", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                // NOTE: the backend expects snake_case keys (aspect_ratio),
                // so we map the camelCase local variable explicitly here.
                body: JSON.stringify({
                    topic,
                    aspect_ratio: aspectRatio,
                    language,
                    gemini_api_key: geminiApiKey,
                    huggingface_api_token: huggingfaceApiToken
                })
            });

            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || "Failed to generate video.");
            }

            loader.classList.add("hidden");
            resultBox.classList.remove("hidden");
            downloadBtn.href = data.video_url;

        } catch (err) {
            alert("Error: " + err.message);
            loader.classList.add("hidden");
        } finally {
            submitBtn.disabled = false;
            submitBtn.classList.remove("opacity-50", "cursor-not-allowed");
        }
    });
});
