/* ============================================================
   Bookshop-M — Client-side JavaScript
   Contains intentional DOM-based XSS vulnerability (B3)
   ============================================================ */

// B3 — DOM-based XSS: Hash fragment injected into innerHTML
document.addEventListener('DOMContentLoaded', function() {
    // Greeting banner from URL hash (VULNERABLE)
    if (window.location.hash) {
        var greeting = decodeURIComponent(window.location.hash.substring(1));
        var el = document.getElementById('greeting-banner');
        if (el) {
            el.innerHTML = greeting;  // DOM XSS — innerHTML with user input
        }
    }

    // Auto-dismiss flash messages after 5 seconds
    var alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Confirm dangerous actions
    var dangerForms = document.querySelectorAll('.danger-confirm');
    dangerForms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            if (!confirm('Are you sure? This action cannot be undone.')) {
                e.preventDefault();
            }
        });
    });

    // Cart quantity validation (client-side only — K1 bypass)
    var qtyInputs = document.querySelectorAll('.qty-input');
    qtyInputs.forEach(function(input) {
        input.addEventListener('change', function() {
            // Client-side check that can be bypassed
            if (this.value < 1) {
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-invalid');
            }
        });
    });

    // Balance check for checkout (client-side only — K5 bypass)
    var checkoutForm = document.getElementById('checkout-form');
    if (checkoutForm) {
        checkoutForm.addEventListener('submit', function(e) {
            var balance = parseFloat(document.getElementById('user-balance').dataset.balance || 0);
            var total = parseFloat(document.getElementById('order-total').dataset.total || 0);
            if (total > balance) {
                // Client-side only check — can be bypassed by modifying hidden total field
                e.preventDefault();
                alert('Insufficient balance! You need $' + (total - balance).toFixed(2) + ' more.');
            }
        });
    }

    // Username availability check (triggers blind SQLi endpoint)
    var usernameInput = document.getElementById('reg-username');
    if (usernameInput) {
        var timeout;
        usernameInput.addEventListener('input', function() {
            clearTimeout(timeout);
            var username = this.value;
            if (username.length > 2) {
                timeout = setTimeout(function() {
                    fetch('/api/check_username?username=' + encodeURIComponent(username))
                        .then(function(r) { return r.json(); })
                        .then(function(data) {
                            var feedback = document.getElementById('username-feedback');
                            if (feedback) {
                                if (data.exists) {
                                    feedback.textContent = 'Username is taken';
                                    feedback.style.color = '#ff0055';
                                } else {
                                    feedback.textContent = 'Username is available';
                                    feedback.style.color = '#00ff41';
                                }
                            }
                        });
                }, 500);
            }
        });
    }

    // Coupon code check (triggers time-based blind SQLi endpoint)
    var couponBtn = document.getElementById('check-coupon-btn');
    if (couponBtn) {
        couponBtn.addEventListener('click', function() {
            var code = document.getElementById('coupon-code-input').value;
            if (code) {
                fetch('/api/check_coupon?code=' + encodeURIComponent(code))
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        var feedback = document.getElementById('coupon-feedback');
                        if (feedback) {
                            if (data.valid) {
                                feedback.textContent = 'Valid! ' + data.discount + '% off';
                                feedback.style.color = '#00ff41';
                            } else {
                                feedback.textContent = 'Invalid coupon';
                                feedback.style.color = '#ff0055';
                            }
                        }
                    });
            }
        });
    }

    // Add matrix rain effect to hero sections
    var heroSection = document.querySelector('.hero-section');
    if (heroSection) {
        createMatrixRain(heroSection);
    }
});

// Matrix rain effect
function createMatrixRain(container) {
    var canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;opacity:0.1;z-index:0;';
    container.style.position = 'relative';
    container.style.overflow = 'hidden';
    container.insertBefore(canvas, container.firstChild);

    var ctx = canvas.getContext('2d');
    canvas.width = container.offsetWidth;
    canvas.height = container.offsetHeight;

    var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*()';
    var fontSize = 14;
    var columns = Math.floor(canvas.width / fontSize);
    var drops = new Array(columns).fill(1);

    function draw() {
        ctx.fillStyle = 'rgba(10, 10, 10, 0.05)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#00ff41';
        ctx.font = fontSize + 'px monospace';

        for (var i = 0; i < drops.length; i++) {
            var text = chars[Math.floor(Math.random() * chars.length)];
            ctx.fillText(text, i * fontSize, drops[i] * fontSize);
            if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                drops[i] = 0;
            }
            drops[i]++;
        }
    }

    setInterval(draw, 50);
}
