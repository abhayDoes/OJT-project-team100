console.log("index.js loaded");

const API = window.location.origin;

// Popup replacement
function notify(msg) {
    alert(msg);
}

// ---------------- SNAPSHOT ---------------- //

document.getElementById("upload-snapshot-btn").onclick = async () => {

    const folderInput = document.getElementById("folder-upload");
    const snapshotId = document.getElementById("snapshot-id").value.trim();

    if (!folderInput.files.length)
        return notify("Please select a folder.");

    if (!snapshotId)
        return notify("Please enter Snapshot ID.");

    const form = new FormData();
    form.append("id", snapshotId);

    for (const file of folderInput.files) {
        form.append("files[]", file, file.webkitRelativePath);
    }

    const res = await fetch(`${API}/snapshot/upload-folder`, {
        method: "POST",
        body: form
    });

    const out = await res.json().catch(() => ({}));

    if (!res.ok) return notify(out.error || "Snapshot failed");

    document.getElementById("snapshot-status").textContent =
        `Snapshot created with ${out.file_count} files`;
    notify("Snapshot created!");
};
