import argparse

from app.services.store import store


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a seven-day citation-audit access key.")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--audits", type=int, default=0, help="0 means unlimited")
    args = parser.parse_args()
    raw_key, record = store.create_access_key(
        max_completed_audits=args.audits,
        valid_days=args.days,
    )
    print(raw_key)
    print(
        f"id={record.id} valid_days={record.valid_days} "
        f"quota={record.max_completed_audits or 'unlimited'}"
    )


if __name__ == "__main__":
    main()
