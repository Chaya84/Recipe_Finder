import unittest
from unittest.mock import patch, MagicMock
import requests

import main


class DummyRoot:
    def after(self, delay, func):
        # call immediately
        func()


class TestRecipeFinder(unittest.TestCase):
    def setUp(self):
        # prepare dummy UI components and frames
        main.root = DummyRoot()
        main.entry = MagicMock()
        # filters
        main.diet_var = MagicMock()
        # frame placeholders
        main.results_container = MagicMock()
        main.details_canvas = MagicMock()
        main.details_content = MagicMock()
        main.nutrition_content = MagicMock()
        main.login_error_label = MagicMock()
        # clear global storage
        main.recipes_data = []

    @patch('main.requests.get')
    def test_fetch_recipes_success(self, mock_get):
        # prepare fake response
        fake_resp = MagicMock()
        fake_resp.raise_for_status.return_value = None
        fake_resp.json.return_value = {'results': [{'id': 10, 'title': 'Soup'}]}
        mock_get.return_value = fake_resp

        # call with filters
        main.fetch_recipes('tomato', filters=['vegetarian'])
        self.assertEqual(main.recipes_data, [{'id': 10, 'title': 'Soup'}])
        mock_get.assert_called_once()
        called_args = mock_get.call_args[1]['params']
        self.assertIn('diet', called_args)

    @patch('main.requests.get')
    def test_fetch_recipes_failure(self, mock_get):
        fake_resp = MagicMock()
        fake_resp.raise_for_status.side_effect = requests.HTTPError("bad")
        mock_get.return_value = fake_resp

        # previous data
        main.recipes_data = [{'id': 1}]
        main.fetch_recipes('test', filters=None)
        # data should remain unchanged
        self.assertEqual(main.recipes_data, [{'id': 1}])

    @patch('main.requests.get')
    def test_fetch_details_calls_display(self, mock_get):
        # set up recipe data
        main.recipes_data = [{'id': 42}]

        # fake info response
        info_resp = MagicMock()
        info_resp.raise_for_status.return_value = None
        info_resp.json.return_value = {'title': 'Cake', 'image': 'http://example.com/img.jpg'}
        # fake nutrition response
        nut_resp = MagicMock()
        nut_resp.raise_for_status.return_value = None
        nut_resp.json.return_value = {'calories': '100kcal', 'carbs': '20g', 'fat': '5g', 'protein': '3g'}

        # requests.get called twice; we supply side effects
        mock_get.side_effect = [info_resp, nut_resp]

        # patch display_details to capture args
        called = []
        def fake_display(info, nutrition):
            called.append((info, nutrition))
        main.display_details = fake_display

        main.fetch_details(0)
        self.assertEqual(len(called), 1)
        self.assertEqual(called[0][0]['title'], 'Cake')
        self.assertIn('calories', called[0][1])

    def test_search_builds_filters(self):
        # configure entry and diet dropdown
        main.entry.get.return_value = 'apple,pear'
        main.diet_var.get.return_value = 'Vegan'

        # patch fetch_recipes to capture passed args
        captured = {}
        def fake_fetch(ingredients, filters):
            captured['ingredients'] = ingredients
            captured['filters'] = filters
        with patch('main.fetch_recipes', new=fake_fetch):
            main.search()

        self.assertEqual(captured['ingredients'], 'apple,pear')
        self.assertListEqual(captured['filters'], ['vegan'])


    def test_validate_login(self):
        self.assertTrue(main.validate_login('u','p'))
        self.assertFalse(main.validate_login('','p'))
        self.assertFalse(main.validate_login('u',''))

    def test_attempt_login_initializes_ui(self):
        main.username_entry = MagicMock()
        main.password_entry = MagicMock()
        main.login_frame = MagicMock()
        main.login_error_label = MagicMock()
        main.username_entry.get.return_value = 'a@a'
        main.password_entry.get.return_value = 'pw'
        with patch('main.build_main_ui') as mock_build, patch('main.show_search_page') as mock_show:
            main.attempt_login()
            mock_build.assert_called_once()
            mock_show.assert_called_once()
            main.login_frame.pack_forget.assert_called_once()

    def test_show_details_triggers_fetch(self):
        with patch('main.show_details_page') as mock_show, patch('main.threading.Thread') as mock_thread:
            main.show_details(5)
            mock_show.assert_called_once()
            self.assertTrue(mock_thread.called)

    @patch('main.tk.Label')
    @patch('main.tk.Button')
    @patch('main.tk.Frame')
    def test_update_results_creates_cards(self, mock_frame, mock_button, mock_label):
        main.results_container = MagicMock()
        main.recipes_data = [{'title':'A'},{'title':'B'}]
        main.update_results()
        self.assertGreaterEqual(mock_frame.call_count, 2)
        self.assertGreaterEqual(mock_button.call_count, 2)

    def test_nutrition_toggle(self):
        main.details_canvas = MagicMock()
        main.nutrition_content = MagicMock()
        main.last_nutrition = {'calories':'100kcal','carbs':'10g','fat':'2g','protein':'5g'}
        with patch('main.plot_nutrition') as mock_plot, patch('main.pd.DataFrame') as mock_df:
            main.show_nutrition_only()
        main.details_canvas.pack_forget.assert_called_once()
        main.nutrition_content.pack.assert_called_once()
        mock_plot.assert_called_once_with(main.last_nutrition, master=main.nutrition_content)
        mock_df.assert_called()

    def test_show_details_section_repacks(self):
        main.nutrition_content = MagicMock()
        main.details_canvas = MagicMock()
        main.show_details_section()
        main.nutrition_content.pack_forget.assert_called_once()
        main.details_canvas.pack.assert_called_once()

    def test_pandas_imported(self):
        import pandas
        self.assertIsNotNone(pandas)

    def test_navigation_helpers(self):
        main.search_frame = MagicMock()
        main.details_frame = MagicMock()
        main.show_search_page()
        main.search_frame.pack.assert_called_once()
        main.show_details_page()
        main.details_frame.pack.assert_called_once()


if __name__ == '__main__':
    unittest.main()
