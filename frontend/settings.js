document.addEventListener('DOMContentLoaded', () => {
    const loginScreen = document.getElementById('login-screen');
    const settingsScreen = document.getElementById('settings-screen');
    const loginForm = document.getElementById('login-form');
    const loginError = document.getElementById('login-error');
    const adminPasswordInput = document.getElementById('admin-password');
    const logoutBtn = document.getElementById('logout-btn');
    const settingsForm = document.getElementById('settings-form');

    function show(el) {
        el.classList.remove('hidden');
    }
    function hide(el) {
        el.classList.add('hidden');
    }

    async function checkAuth() {
        const res = await fetch('/api/admin/check', { credentials: 'include' });
        const data = await res.json();
        return data.authenticated === true;
    }

    async function loadSettings() {
        const res = await fetch('/api/admin/settings', { credentials: 'include' });
        if (!res.ok) throw new Error('Non autorizzato');
        return res.json();
    }

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        hide(loginError);
        const password = adminPasswordInput.value.trim();
        if (!password) return;

        try {
            const res = await fetch('/api/admin/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ password })
            });
            if (!res.ok) {
                const err = await res.json();
                loginError.textContent = err.detail || 'Password errata';
                show(loginError);
                return;
            }
            hide(loginScreen);
            show(settingsScreen);
            await loadAndFillForm();
        } catch (err) {
            loginError.textContent = 'Errore di connessione';
            show(loginError);
        }
    });

    logoutBtn.addEventListener('click', async () => {
        await fetch('/api/admin/logout', { method: 'POST', credentials: 'include' });
        hide(settingsScreen);
        show(loginScreen);
        adminPasswordInput.value = '';
    });

    async function loadAndFillForm() {
        try {
            const s = await loadSettings();
            document.getElementById('camera_d4_host').value = s.camera_d4_host || '';
            document.getElementById('camera_d4_port').value = s.camera_d4_port ?? 80;
            document.getElementById('camera_d4_username').value = s.camera_d4_username || '';
            document.getElementById('camera_d4_password').value = s.camera_d4_password || '';
            document.getElementById('camera_d6_host').value = s.camera_d6_host || '';
            document.getElementById('camera_d6_port').value = s.camera_d6_port ?? 80;
            document.getElementById('camera_d6_username').value = s.camera_d6_username || '';
            document.getElementById('camera_d6_password').value = s.camera_d6_password || '';
            document.getElementById('rule_area_name').value = s.rule_area_name || 'PC-1';
        } catch (err) {
            alert('Errore nel caricamento delle impostazioni.');
        }
    }

    settingsForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            camera_d4_host: document.getElementById('camera_d4_host').value.trim(),
            camera_d4_port: parseInt(document.getElementById('camera_d4_port').value, 10) || 80,
            camera_d4_username: document.getElementById('camera_d4_username').value.trim(),
            camera_d4_password: document.getElementById('camera_d4_password').value,
            camera_d6_host: document.getElementById('camera_d6_host').value.trim(),
            camera_d6_port: parseInt(document.getElementById('camera_d6_port').value, 10) || 80,
            camera_d6_username: document.getElementById('camera_d6_username').value.trim(),
            camera_d6_password: document.getElementById('camera_d6_password').value,
            rule_area_name: document.getElementById('rule_area_name').value.trim() || 'PC-1'
        };

        try {
            const res = await fetch('/api/admin/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error('Salvataggio fallito');
            alert('Impostazioni salvate. Riavvia il backend per applicare.');
        } catch (err) {
            alert('Errore durante il salvataggio.');
        }
    });

    // All'avvio verifica se già autenticato
    (async () => {
        const ok = await checkAuth();
        if (ok) {
            hide(loginScreen);
            show(settingsScreen);
            await loadAndFillForm();
        }
    })();
});
