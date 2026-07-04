# FIND_IT 🔍

A smart web platform for reporting, tracking, and recovering lost and found items.

---

## 📖 Overview

FIND_IT is a web-based Lost and Found Management System that enables users to report lost items, submit found items, search for matching objects, and communicate securely to facilitate item recovery. The platform provides an intuitive interface, secure authentication, and image-based item listings to simplify the lost-and-found process.

---

## ✨ Features

- User Registration and Login
- Secure OTP-based Authentication
- Report Lost Items
- Report Found Items
- Upload Item Images
- Search Lost & Found Listings
- Category-wise Item Management
- Real-time Status Updates
- User Dashboard
- Responsive User Interface
- SQLite Database Integration

---

## 🛠️ Tech Stack

### Frontend
- HTML5
- CSS3
- JavaScript
- Bootstrap
- Jinja2 Templates

### Backend
- Python
- Flask
- Flask-SocketIO

### Database
- SQLite

### Other Technologies
- SMTP Email Service (OTP Verification)
- OpenCV (Image Processing)
- Git & GitHub

---

## 📂 Project Structure

```
FIND_IT
│
├── backend/
│   ├── app.py
│   ├── database/
│   ├── models/
│   ├── routes/
│   ├── services/
│   └── utils/
│
├── frontend/
│   ├── static/
│   ├── templates/
│   └── app.py
│
├── requirements.txt
├── .gitignore
├── README.md
└── .env.example
```

---

## 🚀 Installation

### Clone the Repository

```bash
git clone https://github.com/archana117/FIND_IT.git
```

### Navigate to Project

```bash
cd FIND_IT
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Virtual Environment

Windows

```bash
venv\Scripts\activate
```

Linux / macOS

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Create a `.env` file and configure:

```
EMAIL_ADDRESS=your_email
EMAIL_PASSWORD=your_password
SECRET_KEY=your_secret_key
```

### Run the Application

Backend

```bash
cd backend
python app.py
```

Frontend

```bash
cd frontend
python app.py
```

---

## 📸 Screenshots

Add screenshots of:

- Home Page
- Login Page
- Report Lost Item
- Report Found Item
- Search Results
- Dashboard

---

## 🎯 Future Enhancements

- AI-based Image Matching
- Mobile Application
- Push Notifications
- Location-based Search
- Chat Between Users
- Admin Dashboard
- Analytics Dashboard

---

## 👩‍💻 Author

**Archana Narmeta**

GitHub: https://github.com/archana117

---

