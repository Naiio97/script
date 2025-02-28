document.addEventListener('DOMContentLoaded', function() {
    // Najdeme všechny odkazy na servery
    const serverLinks = document.querySelectorAll('.nav-item');
    
    // Přidáme event listener na každý odkaz
    serverLinks.forEach(link => {
        link.addEventListener('click', async (e) => {
            e.preventDefault();
            
            // Odstranění aktivní třídy ze všech položek
            document.querySelectorAll('.nav-item').forEach(navItem => {
                navItem.classList.remove('active');
            });
            
            // Přidání aktivní třídy na kliknutou položku
            e.target.classList.add('active');
            
            const server = e.target.dataset.server;
            
            try {
                // Načtení certifikátů pro vybraný server
                const response = await fetch(`/get-certificates/${server}`);
                const certificates = await response.json();
                
                // Použijeme existující funkci updateTable místo přímé manipulace s innerHTML
                updateTable(certificates);
            } catch (error) {
                console.error('Chyba při načítání certifikátů:', error);
            }
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
    const daysToExpiry = Math.floor((expiry - today) / (1000 * 60 * 60 * 24));
    
    if (daysToExpiry <= 30) {
        return 'cert-expired';
    } else if (daysToExpiry <= 60) {
        return 'cert-warning';
    } else if (expiry.getFullYear() === today.getFullYear()) {
        return 'cert-ending-year';
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

async function zobrazitDetail(id) {
    try {
        const response = await fetch(`/detail/${id}`);
        const data = await response.text();
        
        const modal = document.getElementById('detailModal');
        const modalBody = modal.querySelector('.modal-body');
        const modalTitle = modal.querySelector('.modal-header h2');
        
        // Nastavíme titulek a obsah
        modalTitle.textContent = 'Detail certifikátu';
        modalBody.innerHTML = data;
        
        modal.style.display = 'block';
        
        // Zavření modálu při kliknutí mimo něj
        window.onclick = function(event) {
            if (event.target == modal) {
                closeModal();
            }
        }
    } catch (error) {
        showImportMessage('Chyba při načítání detailu: ' + error.message);
    }
}

async function upravitCertifikat(id) {
    try {
        const response = await fetch(`/get-edit-form/${id}`);
        const data = await response.text();
        
        const modal = document.getElementById('detailModal');
        const modalBody = modal.querySelector('.modal-body');
        const modalTitle = modal.querySelector('.modal-header h2');
        
        // Nastavíme titulek a obsah
        modalTitle.textContent = 'Upravit certifikát';
        modalBody.innerHTML = data;
        
        // Inicializace datepickeru pro pole s datem
        flatpickr("#expirace", {
            dateFormat: "d.m.Y",
            locale: "cs"
        });
        
        modal.style.display = 'block';
    } catch (error) {
        showImportMessage('Chyba při načítání formuláře: ' + error.message);
    }
}

function closeModal() {
    const modal = document.getElementById('detailModal');
    const modalBody = modal.querySelector('.modal-body');
    const modalTitle = modal.querySelector('.modal-header h2');
    
    // Vyčistíme obsah modálního okna
    modalBody.innerHTML = '';
    modalTitle.textContent = '';
    modal.style.display = 'none';
}

function toggleImport() {
    const importForm = document.getElementById('importForm');
    if (importForm) {
        if (importForm.style.display === 'none' || importForm.style.display === '') {
            importForm.style.display = 'block';
        } else {
            importForm.style.display = 'none';
        }
    }
}

function showImportMessage(message) {
    const messageDiv = document.getElementById('importMessage');
    messageDiv.textContent = message;
    messageDiv.style.display = 'block';
    
    // Skryjeme zprávu po 5 sekundách
    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 5000);
}

async function handleImport(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    try {
        const response = await fetch(form.action, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        if (response.ok) {
            showImportMessage(data.message);
            // Skryjeme formulář
            document.getElementById('importForm').style.display = 'none';
            // Aktualizujeme tabulku pro aktuální server
            const aktivniServer = document.querySelector('.nav-item.active');
            if (aktivniServer) {
                const serverName = aktivniServer.getAttribute('data-server');
                const certResponse = await fetch(`/get-certificates/${serverName}`);
                const certData = await certResponse.json();
                updateTable(certData);
            } else {
                // Pokud není aktivní server, obnovíme stránku
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            }
        } else {
            showImportMessage(data.message || 'Chyba při importu');
        }
    } catch (error) {
        showImportMessage('Chyba při importu: ' + error.message);
    }
}

async function smazatDB() {
    if (confirm('Opravdu chcete smazat celou databázi? Tato akce je nevratná!')) {
        try {
            const response = await fetch('/smazat-db');
            const data = await response.json();
            showImportMessage(data.message);
            
            // Obnovíme stránku po 2 sekundách
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } catch (error) {
            showImportMessage('Chyba při mazání databáze: ' + error.message);
        }
    }
}

async function handleEdit(event, id) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    try {
        const response = await fetch(`/upravit/${id}`, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            showImportMessage(data.message);
            closeModal();
            
            // Aktualizace tabulky
            const aktivniServer = document.querySelector('.nav-item.active');
            if (aktivniServer) {
                const serverName = aktivniServer.getAttribute('data-server');
                const certResponse = await fetch(`/get-certificates/${serverName}`);
                const certData = await certResponse.json();
                updateTable(certData);
            }
        } else {
            const error = await response.json();
            showImportMessage(error.message || 'Chyba při ukládání');
        }
    } catch (error) {
        showImportMessage('Chyba při ukládání: ' + error.message);
    }
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

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
    }
    if (e.ctrlKey && e.key === 'f') {
        document.getElementById('searchInput').focus();
    }
});

async function zobrazitDetailServeru(id) {
    try {
        const response = await fetch(`/get-server-detail/${id}`);
        const data = await response.text();
        
        const modal = document.getElementById('detailModal');
        const modalBody = modal.querySelector('.modal-body');
        const modalTitle = modal.querySelector('.modal-header h2');
        
        modalTitle.textContent = 'Detail serveru';
        modalBody.innerHTML = data;
        
        modal.style.display = 'block';
    } catch (error) {
        showImportMessage('Chyba při načítání detailu: ' + error.message);
    }
}

async function upravitServer(id) {
    try {
        const response = await fetch(`/get-server-edit-form/${id}`);
        const data = await response.text();
        
        const modal = document.getElementById('detailModal');
        const modalBody = modal.querySelector('.modal-body');
        const modalTitle = modal.querySelector('.modal-header h2');
        
        modalTitle.textContent = 'Upravit server';
        modalBody.innerHTML = data;
        
        modal.style.display = 'block';
    } catch (error) {
        showImportMessage('Chyba při načítání formuláře: ' + error.message);
    }
}

async function handleServerEdit(event, id) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    try {
        const response = await fetch(`/upravit-server/${id}`, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            showImportMessage(data.message);
            closeModal();
            
            // Obnovíme stránku pro zobrazení změn
            window.location.reload();
        } else {
            const error = await response.json();
            showImportMessage(error.message || 'Chyba při ukládání');
        }
    } catch (error) {
        showImportMessage('Chyba při ukládání: ' + error.message);
    }
}

function smazatServer(id) {
    if (confirm('Opravdu chcete smazat tento server?')) {
        fetch(`/smazat-server/${id}`)
            .then(response => {
                if (response.ok) {
                    window.location.reload();
                }
            });
    }
} 