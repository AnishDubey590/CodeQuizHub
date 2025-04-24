from . import create_app

# Optional: Load environment variables from a .env file if you use python-dotenv
# from dotenv import load_dotenv
# load_dotenv()

app = create_app() # Call the factory to create the app instance

if __name__ == '__main__':
    # Use app.run() for the development server
    # Debug mode should ideally be controlled by FLASK_ENV or config,
    # but can be set here for simplicity during early development.
    # IMPORTANT: Never run with debug=True in production!
    app.run(debug=True) # You can specify host and port: app.run(host='0.0.0.0', port=8000, debug=True)