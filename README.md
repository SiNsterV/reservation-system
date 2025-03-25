# Barber Shop Reservation System

A simple and efficient reservation system for barber shops. This MVP allows customers to book appointments and barbers to manage their schedules.

## Features

- Customer appointment booking
- Barber schedule management
- Email notifications
- Simple and intuitive interface

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
- Windows:
```bash
venv\Scripts\activate
```
- Unix/MacOS:
```bash
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Initialize the database:
```bash
python init_db.py
```

5. Run the application:
```bash
python app.py
```

## Project Structure

```
.
├── app.py              # Main application file
├── models.py           # Database models
├── forms.py            # Form definitions
├── static/            # Static files (CSS, JS)
├── templates/         # HTML templates
└── instance/         # Database and configuration
``` 