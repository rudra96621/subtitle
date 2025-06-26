document.addEventListener("DOMContentLoaded", function () {
    fetch("/languages")
        .then(response => response.json())
        .then(languages => {
            const spokenLangSelect = document.getElementById("spokenLang");
            const targetLangSelect = document.getElementById("targetLang");

            languages.forEach(lang => {
                let option1 = document.createElement("option");
                option1.value = lang;
                option1.text = lang;
                spokenLangSelect.appendChild(option1);

                let option2 = document.createElement("option");
                option2.value = lang;
                option2.text = lang;
                targetLangSelect.appendChild(option2);
            });
        });
});

function updateProgress(percent) {
    document.getElementById("progressBar").style.width = percent + "%";
    document.getElementById("progressBar").innerText = percent + "%";
}

function resetProgress() {
    document.getElementById("progressBar").style.width = "0%";
    document.getElementById("progressBar").innerText = "";
}

function uploadFile() {
    resetProgress();

    const file = document.getElementById("fileInput").files[0];
    if (!file) {
        alert("Please select a file.");
        return;
    }

    const spokenLang = document.getElementById("spokenLang").value;
    const targetLang = document.getElementById("targetLang").value;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("spoken_lang", spokenLang);
    formData.append("target_lang", targetLang);

    updateProgress(20);

    fetch("/transcribe", {
        method: "POST",
        body: formData
    })
        .then(res => {
            if (!res.ok) {
                throw new Error("Failed to process the file.");
            }
            updateProgress(60);
            return res.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }

            updateProgress(100);

            document.getElementById("transcribedText").value = data.transcribed_text;
            document.getElementById("translatedText").value = data.translated_text;

            document.getElementById("srtDownload").href = `/download/${data.srt_file}`;
            document.getElementById("videoDownload").href = `/download/${data.video_file}`;
            document.getElementById("downloadSection").style.display = "block";
        })
        .catch(err => {
            alert("An error occurred: " + err.message);
            resetProgress();
        });

    

}



