import datetime as dt, unittest
from build_public_reference_bundle import scheduled_due, build
class BundleGates(unittest.TestCase):
    def test_calendar_not_sixty_day_drift(self):
        for year,month,want in [(2026,10,True),(2026,11,False),(2026,12,True),(2027,1,False),(2027,2,True)]:
            self.assertEqual(scheduled_due(2,dt.date(year,month,8)),want)
            self.assertTrue(scheduled_due(1,dt.date(year,month,8)))
    def test_invalid_intervals_and_missing_markets_fail(self):
        for interval in (0,3,-1):
            with self.assertRaises(ValueError):scheduled_due(interval,dt.date(2026,10,8))
        with self.assertRaises(ValueError):build({'AU':None},None)
if __name__=='__main__':unittest.main()
