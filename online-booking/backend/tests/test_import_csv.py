"""Tests for CSV import of masters."""
import csv
import io


class TestImportMastersCSV:
    """Tests for POST /api/v1/admin/masters/import"""

    async def test_import_csv_success(self, client, super_admin_headers, session):
        """Successfully import masters from CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["name", "email", "password", "phone", "telegram_username"])
        writer.writerow(["Master One", "master1@example.com", "SecurePass1!", "+79001111111", "@master1"])
        writer.writerow(["Master Two", "master2@example.com", "SecurePass2!", "+79002222222", "@master2"])

        resp = await client.post(
            "/api/v1/admin/masters/import",
            files={"file": ("masters.csv", output.getvalue(), "text/csv")},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2
        assert data["errors"] == []
        assert data["total_rows"] == 2

    async def test_import_csv_missing_fields(self, client, super_admin_headers):
        """Returns errors for rows with missing required fields."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["name", "email", "password", "phone"])
        writer.writerow(["Master Only Name", "", "SecurePass1!", "+79001111111"])  # missing email
        writer.writerow(["", "master@example.com", "SecurePass1!", "+79002222222"])  # missing name

        resp = await client.post(
            "/api/v1/admin/masters/import",
            files={"file": ("masters.csv", output.getvalue(), "text/csv")},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 0
        assert len(data["errors"]) == 2

    async def test_import_csv_duplicate_email(self, client, super_admin_headers, session, created_master_id):
        """Returns error for duplicate email."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["name", "email", "password", "phone"])
        writer.writerow(["Another Master", "test_master@example.com", "SecurePass1!", "+79001111111"])

        resp = await client.post(
            "/api/v1/admin/masters/import",
            files={"file": ("masters.csv", output.getvalue(), "text/csv")},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 0
        assert len(data["errors"]) == 1
        assert "already exists" in data["errors"][0]["error"]

    async def test_import_csv_non_csv_file(self, client, super_admin_headers):
        """Returns 400 for non-CSV file."""
        resp = await client.post(
            "/api/v1/admin/masters/import",
            files={"file": ("data.txt", "some text", "text/plain")},
            headers=super_admin_headers
        )
        assert resp.status_code == 400
        assert "CSV" in resp.json()["detail"]

    async def test_import_csv_empty_file(self, client, super_admin_headers):
        """Returns success with 0 imported for empty CSV."""
        resp = await client.post(
            "/api/v1/admin/masters/import",
            files={"file": ("empty.csv", "", "text/csv")},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 0
        assert data["total_rows"] == 0

    async def test_import_csv_mixed_success_and_errors(self, client, super_admin_headers):
        """Some rows succeed, some fail."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["name", "email", "password", "phone"])
        writer.writerow(["Valid Master", "valid@example.com", "SecurePass1!", "+79001111111"])
        writer.writerow(["", "invalid@example.com", "SecurePass1!", "+79002222222"])  # missing name
        writer.writerow(["Another Valid", "valid2@example.com", "SecurePass1!", "+79003333333"])

        resp = await client.post(
            "/api/v1/admin/masters/import",
            files={"file": ("masters.csv", output.getvalue(), "text/csv")},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2
        assert len(data["errors"]) == 1
        assert data["total_rows"] == 3
