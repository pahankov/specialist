"""Tests for CSV export tasks."""
from datetime import datetime, timedelta


class TestExportAppointmentsCSV:
    """Tests for export_appointments_csv_task"""

    async def test_export_appointments_empty(self, client, auth_headers, session):
        """Returns CSV with header only when no appointments."""
        resp = await client.get(
            "/api/v1/admin/export/appointments",
            headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        content = resp.text
        assert "ID" in content
        assert "Дата" in content
        assert "Клиент" in content

    async def test_export_appointments_with_status_filter(self, client, auth_headers, session):
        """Returns filtered CSV by status."""
        resp = await client.get(
            "/api/v1/admin/export/appointments",
            params={"status": "completed"},
            headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"

    async def test_export_appointments_with_master_column(self, client, auth_headers, session):
        """Includes master column when requested."""
        resp = await client.get(
            "/api/v1/admin/export/appointments",
            params={"include_master": True},
            headers=auth_headers
        )
        assert resp.status_code == 200
        content = resp.text
        assert "Мастер" in content


class TestExportClientsCSV:
    """Tests for export_clients_csv_task"""

    async def test_export_clients_csv(self, client, auth_headers, session):
        """Returns clients CSV."""
        resp = await client.get(
            "/api/v1/admin/export/clients",
            headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        content = resp.text
        assert "ID" in content
        assert "Имя" in content
        assert "Телефон" in content
        assert "Email" in content
