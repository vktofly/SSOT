import unittest
import pandas as pd
from src.agents import lookup_airline_penalty, predict_sla_breach

class TestRoadmapAgents(unittest.TestCase):
    def test_airline_penalty_rag(self):
        res = lookup_airline_penalty(route="DEL-DXB", carrier="Emirates")
        self.assertIn("cancellation_fee", res)
        self.assertIn("carrier", res)
        self.assertIn("policy_notes", res)
        self.assertEqual(res["carrier"], "Emirates")

    def test_sla_breach_forecaster(self):
        sample_ticket = {
            "Ticket ID": "RF-9999",
            "Logged Date": "2026-06-01",
            "Status": "Pending",
            "Agent": "Test Travel"
        }
        res = predict_sla_breach(sample_ticket, current_date="2026-06-05")
        self.assertTrue(res["is_breached"])
        self.assertGreaterEqual(res["hours_elapsed"], 72)
        self.assertEqual(res["risk_level"], "High")

if __name__ == "__main__":
    unittest.main()
