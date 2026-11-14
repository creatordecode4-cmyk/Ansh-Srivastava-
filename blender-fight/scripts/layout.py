"""Arena layout in metres, read off the TOP-DOWN LAYOUT panel of refs/arena_breakdown.png.
+Y = far end (torii gate), -Y = camera end, X = left/right. Fight area = open centre."""
COURT = dict(x=(-12, 12), y=(-15, 15))          # paved courtyard
FIGHT_CENTER = (0.0, 0.0)                         # open duel area, ~8 m radius kept clear
TORII = dict(pos=(3.0, 13.5), width=8.0, height=7.5)
TORII_STAIRS = dict(pos=(3.0, 17.5), width=9.0, steps=6)
TEMPLE_MAIN = dict(pos=(-17.0, 5.0), size=(9.0, 15.0, 5.0), stairs_y=5.0)   # left, faces +X
TEMPLE_RIGHT = dict(pos=(17.0, 2.0), size=(8.0, 16.0, 4.0))                  # right side halls
TEMPLE_BACK = dict(pos=(3.0, 30.0), size=(14.0, 8.0, 4.5))                   # behind the torii
LANTERNS = [(-7.5, -9.5, False), (7.5, -8.5, True), (-7.0, 3.0, False),
            (8.5, 5.0, False), (-2.0, 11.0, True), (8.0, 11.0, False)]      # (x, y, broken)
CHERRY_TREES = [(-12.5, -14.0), (12.5, -13.0), (13.0, 13.5), (-11.0, 16.0)]
BANNERS = [(-9.5, 9.5), (-9.5, 0.5), (-1.5, 14.5), (7.5, 14.5), (10.5, 8.0), (10.5, -2.0)]
PAPER_LANTERNS = [(-11.6, 1.0, 3.2), (-11.6, 5.0, 3.2), (-11.6, 9.0, 3.2),
                  (12.2, -2.0, 3.0), (12.2, 6.0, 3.0)]
DEBRIS_ZONES = [(-10.0, -11.0), (10.0, -10.0), (-10.5, -3.0), (10.5, 1.0), (-4.0, 12.0), (9.5, 12.0)]
