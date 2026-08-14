import unittest
from src.agents import analyze_partner_sentiment

class TestPartnerSentiment(unittest.TestCase):
    def test_high_urgency_sentiment(self):
        msg = "Bhai refund ka kya hua? 2 hafte ho gaye, koi jawab nahi. My client is threatening legal action!"
        res = analyze_partner_sentiment(msg, agency_tier="VIP")
        
        self.assertIn("sentiment_score", res)
        self.assertIn("urgency_level", res)
        self.assertIn("priority_rank", res)
        self.assertIn("frustration_category", res)
        self.assertEqual(res["urgency_level"], "Critical")
        self.assertEqual(res["priority_rank"], "P0 - Immediate")

    def test_polite_sentiment(self):
        msg = "Good morning, just checking if there is any update on refund RF-1020. Thanks!"
        res = analyze_partner_sentiment(msg, agency_tier="Standard")
        
        self.assertIn("urgency_level", res)
        self.assertIn(res["urgency_level"], ["Low", "Medium"])
        self.assertEqual(res["priority_rank"], "P3 - Standard")

    def test_routine_acknowledgement(self):
        msg = "Noted with thanks, will convey to client."
        res = analyze_partner_sentiment(msg, agency_tier="Standard")
        self.assertIn(res["urgency_level"], ["Low", "Medium"])
        self.assertEqual(res["priority_rank"], "P3 - Standard")



if __name__ == "__main__":
    unittest.main()
