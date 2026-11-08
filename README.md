# ⚖️ LexVoice – Legal Assistance Platform

**LexVoice** is a web-based legal assistance platform designed to make legal information and services more accessible to users. It provides a centralized platform where users can explore different areas of law, submit legal complaints, connect with lawyers, and securely manage their documents.

The platform also includes an administrative dashboard that allows administrators to manage users, lawyers, legal information, and complaints efficiently.

---

## 🚀 Key Features

### 👤 User Module
- User Registration and Login
- Secure Authentication
- User Dashboard
- View and Manage Profile
- Explore Different Categories of Law
- Submit Legal Complaints
- Track Complaint Status
- View Complaint Solutions
- Upload and Manage Personal Documents
- Download and Delete Uploaded Files
- Notifications

### ⚖️ Legal Information Module
- Access different categories of law.
- Explore information about legal rights.
- Learn about constitutional and civil laws.
- Access criminal, cyber, consumer, and family law information.

### 👨‍⚖️ Lawyer Module
- View available lawyers.
- Explore lawyers based on their legal specializations.
- Access junior lawyer information.
- Find relevant legal assistance.

### 🛡️ Admin Module
- Secure Admin Login
- Admin Dashboard
- View Total Users
- View Total Lawyers
- View Total Complaints
- Manage Registered Users
- Add, Edit, and Delete Legal Information
- Manage Lawyers and Junior Lawyers
- View and Manage Complaints
- Provide Complaint Solutions
- Manage Notifications

### 📂 My Files
- Upload legal documents.
- View uploaded documents.
- Download documents.
- Delete unwanted files.
- Securely associate documents with user accounts.

---

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| HTML5 | Website Structure |
| CSS3 | Styling and Design |
| JavaScript | Frontend Functionality |
| Python | Backend Development |
| Flask | Web Framework |
| SQLite | Database Management |
| REST API | Frontend and Backend Communication |
| Visual Studio Code | Development Environment |

---

## 📁 Project Structure

```text
LexVoice/
│
├── frontend/
│   ├── index.html
│   ├── about.html
│   ├── register.html
│   ├── admin-login.html
│   ├── admin.html
│   ├── admin-users.html
│   ├── admin-laws.html
│   ├── admin-lawyers.html
│   ├── admin-complaints.html
│   ├── complaint.html
│   ├── notifications.html
│   └── ...other HTML pages
│
├── backend/
│   ├── app.py
│   ├── lexvoice.db
│   ├── requirements.txt
│   └── uploads/
│
└── README.md
```

*Note: This is an illustrative structure. Your actual folder and file organization may contain additional files.*

---

## ⚙️ Installation and Setup

Follow these steps to run LexVoice on your local machine.

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/LexVoice.git
```

### 2. Navigate to the Project

```bash
cd LexVoice
```

### 3. Navigate to Backend

```bash
cd backend
```

### 4. Create a Virtual Environment

```bash
python -m venv venv
```

### 5. Activate Virtual Environment

For Windows:

```bash
venv\Scripts\activate
```

### 6. Install Dependencies

```bash
pip install -r requirements.txt
```

### 7. Run the Flask Application

```bash
python app.py
```

### 8. Open the Website

Open your browser and visit:

```text
http://127.0.0.1:5000
```

---

## 🗄️ Database

LexVoice uses **SQLite** for database management.

The database stores information related to:

- Registered Users
- Administrators
- Lawyers
- Legal Information
- Complaints
- Uploaded Documents
- Notifications

---

## 🔐 Security Features

- Password hashing
- Session-based authentication
- Protected administrative routes
- User-specific document management
- Secure file handling
- File upload restrictions

---

## 🎯 Project Objectives

1. Make legal information more accessible.
2. Provide a platform to explore different categories of law.
3. Simplify the process of submitting legal complaints.
4. Help users connect with legal professionals.
5. Provide secure document storage and management.
6. Improve complaint management through an administrative dashboard.

---

## 🔮 Future Enhancements

- AI-powered legal assistance.
- Smart legal document analysis.
- Advanced legal search functionality.
- Online lawyer appointment booking.
- Real-time communication with lawyers.
- Improved complaint tracking and analytics.
- Additional legal resources and services.

---

## ⚠️ Disclaimer

LexVoice is an educational and informational platform. The information provided through the platform is not a substitute for professional legal advice. Users should consult qualified legal professionals for assistance with specific legal matters.

---

## 👩‍💻 Developed By

**Sugan Raghupathi**

B.Tech – Computer Science and Engineering

**Project:** LexVoice – Legal Assistance Platform

---

⭐ If you find this project interesting, consider giving the repository a star!

