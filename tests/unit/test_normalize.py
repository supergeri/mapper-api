import pytest
from backend.core.normalize import normalize


@pytest.mark.unit
class TestNormalize:
    """Tests for the normalize function."""

    def test_expand_abbreviations(self):
        """Test that abbreviations are expanded."""
        assert normalize("db bench press") == "dumbbell bench press"
        assert normalize("bb squat") == "barbell squat"
        assert normalize("kb swing") == "kettlebell swing"

    def test_remove_separators(self):
        """Test that separators are converted to spaces."""
        assert normalize("push-up") == "push up"
        assert normalize("push_up") == "push up"
        assert normalize("push/up") == "push up"

    def test_remove_special_characters(self):
        """Test that special characters are removed."""
        assert normalize("bench press!") == "bench press"
        assert normalize("squat (barbell)") == "squat barbell"

    def test_remove_stopwords(self):
        """Test that stopwords are removed."""
        assert normalize("bench press with dumbbell") == "bench press dumbbell"
        assert normalize("squat on machine") == "squat"  # "machine" is also a stopword
        assert normalize("press and squat") == "press squat"

    def test_plural_to_singular(self):
        """Test that plural forms are converted to singular."""
        assert normalize("dumbbell flyes") == "dumbbell flye"
        assert normalize("bench presses") == "bench press"

    def test_case_insensitive(self):
        """Test that normalization is case insensitive."""
        assert normalize("DB BENCH PRESS") == "dumbbell bench press"
        assert normalize("Dumbbell Bench Press") == "dumbbell bench press"

    def test_complex_examples(self):
        """Test complex real-world examples."""
        assert normalize("DB Bench Press (Flat)") == "dumbbell bench press flat"
        assert normalize("Incline DB Flye") == "incline dumbbell flye"
        assert normalize("Push-ups") == "push ups"  # "ups" doesn't have plural mapping

    def test_empty_string(self):
        """Test that empty string returns empty string."""
        assert normalize("") == ""

    def test_whitespace_only(self):
        """Test that whitespace-only strings return empty string."""
        assert normalize("   ") == ""
        assert normalize("\t\n") == ""
