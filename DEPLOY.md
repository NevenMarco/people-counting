# Deploy su Ubuntu (produzione)

Istruzioni per installare e avviare People Counting su un server Ubuntu.

## 1. Prerequisiti

```bash
# Aggiorna il sistema
sudo apt update && sudo apt upgrade -y

# Installa Docker
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Aggiungi il tuo utente al gruppo docker (per evitare sudo)
sudo usermod -aG docker $USER
# Poi disconnettiti e riconnettiti, oppure: newgrp docker
```

## 2. Clona il progetto

```bash
cd /opt  # oppure un'altra cartella a tua scelta
sudo mkdir -p people-counting
sudo chown $USER:$USER people-counting
cd people-counting

git clone https://github.com/NevenMarco/people-counting.git .
```

## 3. Configura le variabili

Modifica `docker-compose.yml` con i valori reali per:

- **DB**: `POSTGRES_PASSWORD` (consigliato: password diversa da `people_pass`)
- **Telecamere D4/D6**: `CAMERA_D4_HOST`, `CAMERA_D4_PASSWORD`, `CAMERA_D6_HOST`, `CAMERA_D6_PASSWORD`, ecc.
- **Admin**: `ADMIN_PASSWORD` (password iniziale per la pagina Admin)

Oppure, crea un file `.env` nella root del progetto e usa variabili:

```bash
# .env (non committare, aggiungi a .gitignore se non presente)
POSTGRES_PASSWORD=tua_password_sicura
ADMIN_PASSWORD=tua_password_admin
# Se le telecamere non sono in docker-compose, configura da UI Admin dopo il primo avvio
```

Per usare `.env` nel docker-compose, sostituisci i valori hardcoded con `${ADMIN_PASSWORD}` ecc.

## 4. Avvia i container

```bash
cd /opt/people-counting
docker compose up -d --build
```

Verifica che i container siano in esecuzione:

```bash
docker compose ps
```

## 5. Esposizione in produzione

- **Porta 8080**: backend e frontend sono esposti su `http://SERVER_IP:8080`
- **Nginx reverse proxy** (opzionale): per HTTPS e dominio personalizzato

Esempio minimo Nginx:

```nginx
server {
    listen 80;
    server_name tuo-dominio.it;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 6. Firewall

```bash
sudo ufw allow 8080/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

## 7. Aggiornamenti futuri

```bash
cd /opt/people-counting
git pull
docker compose build backend
docker compose up -d
```

## Note

- La **password admin** può essere cambiata dalla pagina Admin (`/settings.html`).
- Le **impostazioni telecamere** possono essere modificate dalla UI Admin e richiedono un riavvio del backend (pulsante "Riavvia backend" nella stessa pagina).
- Il **riavvio Docker** dalla UI funziona solo se il backend gira in Docker e ha accesso a `/var/run/docker.sock` (già configurato nel compose).
