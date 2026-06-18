from app.services.alert_notifications import run_saved_search_notifications_once


def main() -> None:
    result = run_saved_search_notifications_once()
    print(result)


if __name__ == "__main__":
    main()
