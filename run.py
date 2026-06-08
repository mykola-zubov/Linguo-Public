from app import create_app

app = create_app()

if __name__ == "__main__":
    print("--- ЗАПУСК СЕРВЕРА... ---")
    print("Відкрийте в браузері: http://127.0.0.1:5000")
    app.run(debug=True, port=5000)