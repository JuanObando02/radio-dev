async function login() {
    const password = document.getElementById('password').value;
    const errorEl = document.getElementById('error');
    errorEl.textContent = '';
    
    try {
        const res = await fetch('/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password })
        });
        const data = await res.json();
        if (data.ok) {
            localStorage.setItem('admin_token', data.token);
            window.location.href = '/admin';
        } else {
            errorEl.textContent = 'Contraseña incorrecta';
        }
    } catch (e) {
        console.error(e);
        errorEl.textContent = 'Error de conexión';
    }
}
