/* Downscale large image uploads in the browser before submit.
 *
 * Vercel rejects request bodies over 4.5 MB, and a modern phone photo is
 * routinely larger than that. Resizing to 2000 px / JPEG 0.85 here keeps the
 * Django form flow unchanged and avoids a failed upload on slow connections.
 */
(function () {
    'use strict';

    var MAX_EDGE = 2000;
    var QUALITY = 0.85;
    var SKIP_BELOW_BYTES = 1024 * 1024;   // small files are fine as-is

    function shouldProcess(file) {
        if (!file || !file.type || file.type.indexOf('image/') !== 0) return false;
        if (file.type === 'image/gif' || file.type === 'image/svg+xml') return false;
        return file.size > SKIP_BELOW_BYTES;
    }

    function loadBitmap(file) {
        if (window.createImageBitmap) {
            return createImageBitmap(file);
        }
        return new Promise(function (resolve, reject) {
            var url = URL.createObjectURL(file);
            var img = new Image();
            img.onload = function () {
                URL.revokeObjectURL(url);
                resolve(img);
            };
            img.onerror = function () {
                URL.revokeObjectURL(url);
                reject(new Error('decode failed'));
            };
            img.src = url;
        });
    }

    function encode(canvas, type) {
        return new Promise(function (resolve) {
            canvas.toBlob(resolve, type, QUALITY);
        });
    }

    function downscale(file) {
        return loadBitmap(file).then(function (bitmap) {
            var width = bitmap.width || bitmap.naturalWidth;
            var height = bitmap.height || bitmap.naturalHeight;
            var scale = Math.min(1, MAX_EDGE / Math.max(width, height));
            if (scale === 1) return file;

            var canvas = document.createElement('canvas');
            canvas.width = Math.round(width * scale);
            canvas.height = Math.round(height * scale);
            canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);

            // Keep PNG (transparency); everything else becomes JPEG.
            var type = file.type === 'image/png' ? 'image/png' : 'image/jpeg';
            return encode(canvas, type).then(function (blob) {
                if (!blob) return file;
                var name = file.name.replace(/\.[^.]+$/, '') + (type === 'image/png' ? '.png' : '.jpg');
                return new File([blob], name, { type: type, lastModified: Date.now() });
            });
        }).catch(function () {
            return file;   // never block the upload on a decode failure
        });
    }

    document.addEventListener('change', function (event) {
        var input = event.target;
        if (!input || input.tagName !== 'INPUT' || input.type !== 'file') return;
        if (!input.files || input.files.length !== 1) return;

        var file = input.files[0];
        if (!shouldProcess(file)) return;

        downscale(file).then(function (processed) {
            if (processed === file) return;
            try {
                var transfer = new DataTransfer();
                transfer.items.add(processed);
                input.files = transfer.files;
            } catch (error) {
                /* Older browsers: fall back to the original file. */
            }
        });
    });
})();
