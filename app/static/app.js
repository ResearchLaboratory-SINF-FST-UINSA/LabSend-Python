/**
 * LabSend Print Transfer - App JavaScript
 * Client-side functionality
 */

// Toast notification system
class Toast {
    static show(message, duration = 2500) {
        const toast = document.getElementById('toast');
        if (!toast) return;

        toast.textContent = message;
        toast.classList.remove('hidden');
        toast.style.opacity = '1';

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.classList.add('hidden'), 300);
        }, duration);
    }

    static success(message) {
        this.show(message);
    }

    static error(message) {
        this.show(message, 4000);
    }
}

// API helper
const API = {
    async get(url) {
        const res = await fetch(url);
        if (!res.ok) throw new Error(await res.text());
        return res.json();
    },

    async post(url, data) {
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error(await res.text());
        return res.json();
    },

    async postForm(url, formData) {
        const res = await fetch(url, {
            method: 'POST',
            body: formData
        });
        if (!res.ok) throw new Error(await res.text());
        return res.json();
    }
};

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Format datetime
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('id-ID', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// File validation
const FileValidator = {
    maxSize: 50 * 1024 * 1024, // 50MB
    allowedExtensions: ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'],

    isValidExtension(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        return this.allowedExtensions.includes(ext);
    },

    isValidSize(size) {
        return size <= this.maxSize;
    },

    validate(filename, size) {
        const errors = [];

        if (!this.isValidExtension(filename)) {
            errors.push(`File ${filename} tidak diizinkan`);
        }

        if (!this.isValidSize(size)) {
            errors.push(`File ${filename} terlalu besar (max 50MB)`);
        }

        return {
            valid: errors.length === 0,
            errors
        };
    }
};

// Upload handler with progress
class UploadHandler {
    constructor(options = {}) {
        this.url = options.url;
        this.onProgress = options.onProgress || (() => {});
        this.onComplete = options.onComplete || (() => {});
        this.onError = options.onError || (() => {});
    }

    async upload(files) {
        const formData = new FormData();

        files.forEach((file, index) => {
            formData.append(`file_${index}`, file);
        });

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    this.onProgress(percent, e.loaded, e.total);
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        this.onComplete(data);
                        resolve(data);
                    } catch (e) {
                        this.onError('Invalid response');
                        reject(e);
                    }
                } else {
                    const error = xhr.responseText || 'Upload failed';
                    this.onError(error);
                    reject(new Error(error));
                }
            });

            xhr.addEventListener('error', () => {
                const error = 'Network error';
                this.onError(error);
                reject(new Error(error));
            });

            xhr.open('POST', this.url);
            xhr.send(formData);
        });
    }
}

// QR Scanner (for future use)
class QRScanner {
    constructor(videoElement, onScan) {
        this.video = videoElement;
        this.onScan = onScan;
        this.stream = null;
    }

    async start() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }
            });
            this.video.srcObject = this.stream;
            this.video.play();
            this.scan();
        } catch (err) {
            console.error('Camera access denied:', err);
        }
    }

    stop() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
    }

    scan() {
        // Placeholder for QR scanning logic
        // Would use a library like jsQR
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-auto-dismiss');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// Export for use in other scripts
window.LabSend = {
    Toast,
    API,
    formatFileSize,
    formatDateTime,
    debounce,
    FileValidator,
    UploadHandler,
    QRScanner
};