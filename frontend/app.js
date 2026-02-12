document.addEventListener('DOMContentLoaded', () => {
    const totalCountEl = document.getElementById('total-count');
    const settingsBtn = document.getElementById('settings-btn');
    const settingsPanel = document.getElementById('settings-panel');
    const setBtn = document.getElementById('set-btn');
    const occupancyInput = document.getElementById('occupancy-input');
    
    // Toggle settings panel
    settingsBtn.addEventListener('click', () => {
        const isHidden = settingsPanel.classList.toggle('hidden');
        if (!isHidden) {
            // Pre-fill input with current count
            occupancyInput.value = totalCountEl.innerText;
            occupancyInput.focus();
        }
    });

    // Set functionality
    setBtn.addEventListener('click', async () => {
        const newValue = parseInt(occupancyInput.value, 10);
        if (isNaN(newValue) || newValue < 0) {
            alert('Inserisci un numero valido.');
            return;
        }

        try {
            const res = await fetch('/api/set-occupancy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ occupancy: newValue })
            });
            
            if (!res.ok) throw new Error('Set failed');
            
            // Immediately update UI
            totalCountEl.textContent = newValue;
            // Hide panel
            settingsPanel.classList.add('hidden');
            
        } catch (err) {
            console.error(err);
            alert('Errore durante l\'aggiornamento.');
        }
    });

    // Polling function
    async function fetchPresence() {
        try {
            const res = await fetch('/api/presence');
            if (!res.ok) throw new Error('Network response was not ok');
            const data = await res.json();
            
            // Animate number change if needed, for now just set text
            totalCountEl.textContent = data.presenti_totali;
            
        } catch (err) {
            console.error('Error fetching presence:', err);
            // Optionally show error state
        }
    }

    // Initial fetch
    fetchPresence();

    // Poll every 2 seconds
    setInterval(fetchPresence, 2000);
});
