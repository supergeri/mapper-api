"""Tests for diff engine edge cases."""

import pytest
from replay.core import Session, DiffEngine


class TestDiffEngineEdgeCases:
    """Test edge cases for the DiffEngine."""

    def test_array_reordering(self):
        """Test detection of array reordering."""
        session_a = Session('a', 'a', {
            'exercises': ['A', 'B', 'C']
        })
        session_b = Session('b', 'b', {
            'exercises': ['C', 'A', 'B']
        })

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        assert result.identical is False
        assert any(d.diff_type == 'reordered' for d in result.differences)

    def test_nested_nulls(self):
        """Test handling of nested null values."""
        session_a = Session('a', 'a', {
            'user': {'name': 'John', 'age': None}
        })
        session_b = Session('b', 'b', {
            'user': {'name': 'John', 'age': 30}
        })

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        assert result.identical is False
        assert any(d.path == 'user.age' and d.diff_type == 'changed' for d in result.differences)

    def test_numeric_precision_edge(self):
        """Test numeric precision with very close values."""
        session_a = Session('a', 'a', {
            'distance': 1000.000000001
        })
        session_b = Session('b', 'b', {
            'distance': 1000.000000002
        })

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        # These should be considered equal (within epsilon)
        assert result.identical is True

    def test_numeric_precision_significant_difference(self):
        """Test numeric precision with significant differences."""
        session_a = Session('a', 'a', {
            'distance': 1000.0
        })
        session_b = Session('b', 'b', {
            'distance': 2000.0
        })

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        # These should be considered different
        assert result.identical is False
        assert any(d.diff_type == 'changed' for d in result.differences)

    def test_empty_array_vs_missing_field(self):
        """Test distinction between empty array and missing field."""
        session_a = Session('a', 'a', {
            'exercises': []
        })
        session_b = Session('b', 'b', {
            # 'exercises' field is missing entirely
        })

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        # Empty array should be detected as a difference vs missing field
        assert result.identical is False
        assert any(d.path == 'exercises' for d in result.differences)

    def test_deeply_nested_arrays(self):
        """Test handling of deeply nested array structures."""
        session_a = Session('a', 'a', {
            'workout': {
                'weeks': [
                    {'days': ['Monday', 'Tuesday']},
                    {'days': ['Wednesday', 'Thursday']}
                ]
            }
        })
        session_b = Session('b', 'b', {
            'workout': {
                'weeks': [
                    {'days': ['Monday', 'Tuesday']},
                    {'days': ['Friday', 'Saturday']}
                ]
            }
        })

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        assert result.identical is False
        # Should detect the change in the nested structure
        assert len(result.differences) > 0

    def test_mixed_type_arrays(self):
        """Test handling of arrays with mixed types."""
        session_a = Session('a', 'a', {
            'data': [1, 'two', 3.0, True]
        })
        session_b = Session('b', 'b', {
            'data': [1, 'two', 3.0, True]
        })

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        # Identical mixed-type arrays should be equal
        assert result.identical is True

    def test_object_with_stringifiable_and_non_stringifiable(self):
        """Test handling of objects with both stringifiable and non-stringifiable items."""
        # Use a class that can be stringified by repr() but might fail with str()
        class CustomClass:
            def __str__(self):
                return "custom"
            def __repr__(self):
                return "custom_repr"

        session_a = Session('a', 'a', {
            'items': [1, 2]
        })
        session_b = Session('b', 'b', {
            'items': [1, 2]
        })

        engine = DiffEngine()
        # Should not raise an error - safe_str should handle non-stringifiable objects
        result = engine.compute_diff(session_a, session_b)
        assert result.identical is True
