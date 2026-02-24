# Steemit Posting API

Lightweight Python API server for posting to Steemit via **n8n HTTP Request** or any HTTP client. Runs in Docker on Ubuntu server.

---

## Steem Blockchain Limits

| Field | Limit |
|-------|-------|
| **Body** | ~65,535 bytes (~60,000+ English characters / ~10,000 words) |
| **Title** | 256 bytes |
| **Permlink** | 256 characters (auto-generated) |
| **Tags** | Max **5** tags, each lowercase `a-z0-9-` only |
| **JSON Metadata** | 65,535 bytes |

---

## API Endpoints

### `GET /health`

Server status check. No authentication required.

**Response:**
```json
{
  "status": "ok",
  "author": "your-username",
  "key_configured": true
}
```

---

### `POST /post`

Create a new Steemit post. Requires `X-API-Key` header.

**Headers:**

| Header | Value | Required |
|--------|-------|----------|
| `Content-Type` | `application/json` | ✅ Yes |
| `X-API-Key` | Your `STEEM_POSTING_KEY` | ✅ Yes |

**Request Body (JSON):**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `title` | string | ✅ Yes | — | Post title (max 256 bytes) |
| `body` | string | ✅ Yes | — | Post content, Markdown supported (max ~65KB) |
| `tags` | string[] | ❌ No | `["steemit"]` | Max 5 tags, lowercase `a-z0-9-` only |
| `community` | string | ❌ No | `null` | Community name, e.g. `"hive-000000"` |
| `self_vote` | boolean | ❌ No | `false` | Auto-upvote as author after posting |
| `beneficiaries` | object[] | ❌ No | `null` | Reward split, e.g. `[{"account":"user1","weight":5000}]` |

> **Note:** `weight` in beneficiaries is in basis points: `5000` = 50%, `10000` = 100%

**Example Request:**
```json
{
  "title": "My First Post",
  "body": "Hello Steemit! This is my **first post** using the API.\n\n![image](https://example.com/photo.jpg)",
  "tags": ["steemit", "blog", "introduction"],
  "community": "hive-172186",
  "self_vote": false
}
```

**Success Response (201):**
```json
{
  "success": true,
  "author": "your-username",
  "permlink": "my-first-post-1740000000-a1b2c3",
  "url": "https://steemit.com/@your-username/my-first-post-1740000000-a1b2c3",
  "tags": ["steemit", "blog", "introduction"]
}
```

**Error Responses:**

| Status | Cause |
|--------|-------|
| `400` | Missing title/body, invalid account |
| `401` | Invalid or missing `X-API-Key` |
| `500` | Server misconfigured or Steem network error |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `STEEM_POSTING_KEY` | ✅ Yes | Your Steemit posting key. Also used as `X-API-Key` for auth |
| `STEEM_AUTHOR` | ✅ Yes | Your Steemit username (without @) |
| `PORT` | ❌ No | Server port (default: `5000`) |

---

## Setup — Local

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env file
cp .env.example .env
# Edit .env with your Posting Key and Username

# 3. Start server
python server.py
```

---

## Setup — Docker (Ubuntu Server)

### First Time

```bash
# 1. Upload files to server
scp -r . user@your-server:/opt/steemit-api/

# 2. SSH into server
ssh user@your-server

# 3. Create .env
cd /opt/steemit-api
cp .env.example .env
nano .env   # Set your credentials
```

### Run with Docker Compose

```bash
# Build and start
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down

# Restart
docker compose restart
```

### Run with Docker (without Compose)

```bash
docker build -t steemit-api .

docker run -d \
  --name steemit-api \
  --restart unless-stopped \
  -p 5000:5000 \
  --env-file .env \
  steemit-api
```

---

## n8n Integration

Configure **HTTP Request** node:

| Field | Value |
|-------|-------|
| Method | `POST` |
| URL | `http://YOUR_SERVER_IP:5000/post` |
| Authentication | Header Auth |
| Header Name | `X-API-Key` |
| Header Value | Your `STEEM_POSTING_KEY` from `.env` |
| Body Type | JSON |

**n8n JSON Body Example:**
```json
{
  "title": "{{ $json.title }}",
  "body": "{{ $json.body }}",
  "tags": ["steemit", "blog"]
}
```

**Test with curl:**
```bash
curl -X POST http://localhost:5000/post \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_POSTING_KEY" \
  -d '{
    "title": "Test Post",
    "body": "Hello from the API!",
    "tags": ["steemit", "test"]
  }'
```

---

## Security

- `STEEM_POSTING_KEY` is used for **both** Steemit posting and API authentication
- **Never expose this key publicly** — anyone with it can post to your account
- Use a firewall to restrict port 5000:
  ```bash
  sudo ufw allow from YOUR_N8N_IP to any port 5000
  ```

---

## Project Structure

```
├── server.py           # Main API server
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker image config
├── docker-compose.yml  # Docker Compose config
├── .env.example        # Environment template
├── .env                # Your credentials (gitignored)
├── .gitignore
└── README.md
```

## Steem API Nodes

The server connects to these nodes with automatic fallback:

1. `https://api.steemit.com`
2. `https://api.steemyy.com`
3. `https://api.justyy.com`
4. `https://steem.justyy.com`
