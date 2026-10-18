from presstoshape.views.window_placement import DEFAULT_SIZE, fit_on_screens

LAPTOP = (0, 0, 1920, 1050)
MONITOR_RIGHT = (1920, 0, 2560, 1400)


def test_first_start_centers_the_default_size_on_the_primary_screen():
    x, y, width, height = fit_on_screens(None, [LAPTOP])
    assert (width, height) == DEFAULT_SIZE
    assert (x, y) == ((1920 - width) // 2, (1050 - height) // 2)


def test_a_visible_window_stays_where_it_was():
    assert fit_on_screens((100, 80, 1200, 800), [LAPTOP, MONITOR_RIGHT]) == (100, 80, 1200, 800)
    assert fit_on_screens((2200, 100, 1600, 900), [LAPTOP, MONITOR_RIGHT]) == (2200, 100, 1600, 900)


def test_a_window_hanging_partly_off_screen_stays_if_its_title_bar_is_reachable():
    assert fit_on_screens((1500, 600, 1200, 800), [LAPTOP]) == (1500, 600, 1200, 800)


def test_window_on_an_unplugged_monitor_moves_to_the_primary_screen():
    x, y, width, height = fit_on_screens((2200, 100, 1600, 900), [LAPTOP])
    assert (width, height) == (1600, 900)
    assert 0 <= x and x + width <= 1920 and 0 <= y and y + height <= 1050


def test_window_dragged_up_and_away_is_brought_back():
    x, y, width, height = fit_on_screens((300, -900, 1000, 700), [LAPTOP])
    assert y >= 0 and (width, height) == (1000, 700)


def test_window_bigger_than_a_smaller_new_screen_is_shrunk_and_pulled_in():
    assert fit_on_screens((100, 50, 2400, 1300), [LAPTOP]) == (0, 0, 1920, 1050)


def test_window_mostly_on_a_secondary_screen_is_centered_there():
    x, y, width, height = fit_on_screens((1800, -500, 1000, 700), [LAPTOP, MONITOR_RIGHT])
    assert x >= 1920 and x + width <= 1920 + 2560


def test_broken_saved_size_falls_back_to_default():
    assert fit_on_screens((10, 10, 0, 500), [LAPTOP])[2:] == DEFAULT_SIZE
