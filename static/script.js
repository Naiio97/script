document.addEventListener('DOMContentLoaded', function() {
    // Najdeme všechny odkazy na servery
    const serverLinks = document.querySelectorAll('.nav-item');
    
    // Přidáme event listener na každý odkaz
    serverLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Získáme název serveru
            const server = this.getAttribute('data-server');
            
            // Aktualizujeme aktivní třídu
            serverLinks.forEach(l => l.classList.remove('active'));
            this.classList.add('active');
            
            // Načteme certifikáty pro vybraný server
            fetch(`/get-certificates/${server}`)
                .then(response => response.json())
                .then(data => {
                    // Aktualizujeme tabulku
                    updateTable(data);
                })
                .catch(error => console.error('Error:', error));
        });
    });
});

function formatDate(dateStr) {
    const date = new Date(dateStr);
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
}

function getExpiryClass(expiryDate) {
    const today = new Date();
    const expiry = new Date(expiryDate);
    const daysUntilExpiry = Math.floor((expiry - today) / (1000 * 60 * 60 * 24));
    
    if (expiry < today || daysUntilExpiry <= 30) {  // Prošlé nebo končí tento měsíc
        return 'expired';
    } else if (daysUntilExpiry <= 60) {  // Končí příští měsíc
        return 'expiring-warning';
    }
    return '';
}

function updateTable(certificates) {
    const tbody = document.querySelector('table tbody');
    tbody.innerHTML = '';
    
    certificates.forEach(cert => {
        const row = document.createElement('tr');
        row.className = getExpiryClass(cert.expirace);  // Přidáme třídu podle expirace
        row.innerHTML = `
            <td>${cert.server}</td>
            <td>${cert.cesta}</td>
            <td>${cert.nazev}</td>
            <td class="date">${formatDate(cert.expirace)}</td>
            <td class="actions">
                <button class="button small info" onclick="zobrazitDetail('${cert.id}')" title="Detail">
                    <i class="fas fa-eye"></i>
                </button>
                <button class="button small primary" onclick="upravitCertifikat('${cert.id}')" title="Upravit">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="button small danger" onclick="smazatCertifikat('${cert.id}')" title="Smazat">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function upravitCertifikat(id) {
    window.location.href = `/upravit/${id}`;
}

function smazatCertifikat(id) {
    if (confirm('Opravdu chcete smazat tento certifikát?')) {
        fetch(`/smazat/${id}`)
            .then(response => {
                if (response.ok) {
                    // Znovu načteme aktuální server
                    const aktivniServer = document.querySelector('.nav-item.active').getAttribute('data-server');
                    fetch(`/get-certificates/${aktivniServer}`)
                        .then(response => response.json())
                        .then(data => updateTable(data));
                }
            });
    }
}

function zobrazitDetail(id) {
    window.location.href = `/detail/${id}`;
} 