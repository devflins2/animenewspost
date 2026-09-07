# 🚀 Render Deployment Guide (Step-by-Step)

Aapka project **Render (render.com)** par 24/7 deploy hone ke liye 100% ready hai! 
Jab aap ise Render par deploy karenge, toh:
1. Yeh background me **24/7 continuous hourly auto-post** karta rahega.
2. Aapko ek live public dashboard URL milega (jaise `https://anime-news-autopost.onrender.com`), jise aap apne phone ya laptop par kabhi bhi open karke posts dekh aur control kar sakte hain.

---

## 📌 Step 1: Code ko GitHub par Push Karein

1. Apne folder me Git initialize karein (agar pehle se nahi hai):
   ```bash
   git init
   git add .
   git commit -m "Anime News Auto-Poster Ready for Render"
   ```
2. GitHub par ek naya repository create karein (e.g. `anime-news-autopost`).
3. GitHub repo link add karke push karein:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/anime-news-autopost.git
   git branch -M main
   git push -u origin main
   ```

---

## 📌 Step 2: Render par Web Service Banayein

1. **[dashboard.render.com](https://dashboard.render.com/)** par login karein.
2. Top right me **"New +"** button par click karein aur **"Web Service"** select karein.
3. Apna GitHub repository connect/select karein.
4. Niche diye gaye settings fill karein:

| Setting | Value |
| :--- | :--- |
| **Name** | `anime-news-autopost` (ya koi bhi naam) |
| **Region** | Singapore / Frankfurt / Oregon (Koi bhi) |
| **Branch** | `main` |
| **Runtime** | `Python` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python server.py` |
| **Instance Type** | `Free` |

---

## 📌 Step 3: Environment Variables Add Karein

Render dashboard par **"Environment"** ya **"Advanced"** section me jayein aur yeh Variables add karein:

| Key | Value |
| :--- | :--- |
| `INSTAGRAM_ACCESS_TOKEN` | `IGAAedIr6g2UxBZAGE2NTJRVjltemhXaEJNQnMwWTFwem14WUtMZAi1kdzVQUkJmMjQxLUtYQmZAFdXVBS1NBTk04ZAnJyMF9WSUdXZAS1PczhQbU80LVZAWeG1tYUJfNGxqQjM4aGRReUtSVnd0WVpFRERqT1dBM2xTWl9EalZAXb1VyZAwZDZD` |
| `INSTAGRAM_ACCOUNT_ID` | `28339864398979335` |
| `INSTAGRAM_HANDLE` | `@anireport_` |
| `ANIME_API_URL` | `https://animeapinews.onrender.com/api/v1/posts` |
| `IMAGE_ASPECT_RATIO` | `4:5` |
| `POST_INTERVAL_MINUTES` | `60` |
| `MAX_RETRIES` | `3` |
| `RETRY_DELAY_SECONDS` | `15` |

---

## 📌 Step 4: Deploy & Live!

1. Niche **"Create Web Service"** par click karein.
2. Render build start karega aur 1-2 minute me deploy ho jayega!
3. Render logs me aapko dikhega:
   ```text
   [Scheduler] 🚀 24/7 Automated Background Auto-Poster Started!
   Listening on http://0.0.0.0:10000
   ```
4. Render aapko ek live URL dega (e.g. `https://anime-news-autopost.onrender.com`).

---

## 💡 Pro-Tip: Render Free Tier ko 24/7 Awake Kaise Rakhein?

Render Free Tier 15 minute ke inactivity ke baad sleep mode me chala jata hai. Ise hamesha active rakhne ke liye:
1. **[UptimeRobot.com](https://uptimerobot.com/)** ya **[cron-job.org](https://cron-job.org/)** (100% Free) par jayein.
2. New Monitor create karein:
   - **Type**: `HTTP(s)`
   - **URL**: `https://YOUR-APP-NAME.onrender.com/health`
   - **Interval**: `Every 5 minutes`
3. Ab Render kabhi sleep nahi hoga aur 24/7 uninterrupted hourly anime posts karta rahega!
