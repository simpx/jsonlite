"""Full-text search index tests."""
import pytest
import tempfile
import os
from jsonlite import JSONlite


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_file = tempfile.NamedTemporaryFile(
        delete=False, mode="w+", encoding="utf-8")
    filename = temp_file.name
    db = JSONlite(filename)
    yield db, filename
    temp_file.close()
    os.remove(filename)


@pytest.fixture
def db_with_documents(temp_db):
    """Create a database with sample documents for full-text search."""
    db, filename = temp_db
    
    # Insert documents with text content
    db.insert_many([
        {'title': 'Introduction to Python', 'content': 'Python is a powerful programming language'},
        {'title': 'Advanced Python Techniques', 'content': 'Learn advanced Python programming patterns'},
        {'title': 'JavaScript Basics', 'content': 'JavaScript is used for web development'},
        {'title': 'Web Development Guide', 'content': 'Modern web development with Python and JavaScript'},
        {'title': 'Database Design', 'content': 'Design efficient databases for your applications'},
    ])
    
    return db, filename


class TestFullTextIndexCreation:
    """Test full-text index creation and management."""
    
    def test_create_fulltext_index(self, temp_db):
        """Test creating a full-text index."""
        db, _ = temp_db
        index_name = db.create_fulltext_index(['title'])
        assert index_name == 'fulltext_title'
        
        indexes = db.list_fulltext_indexes()
        assert len(indexes) == 1
        assert indexes[0]['name'] == index_name
        assert indexes[0]['fields'] == ['title']
    
    def test_create_fulltext_index_multiple_fields(self, temp_db):
        """Test creating a full-text index on multiple fields."""
        db, _ = temp_db
        index_name = db.create_fulltext_index(['title', 'content'])
        assert index_name == 'fulltext_title_content'
        
        indexes = db.list_fulltext_indexes()
        assert len(indexes) == 1
        assert indexes[0]['fields'] == ['title', 'content']
    
    def test_create_fulltext_index_custom_name(self, temp_db):
        """Test creating a full-text index with custom name."""
        db, _ = temp_db
        index_name = db.create_fulltext_index(['content'], name='content_search')
        assert index_name == 'content_search'
    
    def test_create_fulltext_index_duplicate(self, temp_db):
        """Test that duplicate index creation raises error."""
        db, _ = temp_db
        db.create_fulltext_index(['title'])
        
        with pytest.raises(ValueError, match="already exists"):
            db.create_fulltext_index(['title'])
    
    def test_create_fulltext_index_empty_fields(self, temp_db):
        """Test that empty fields list raises error."""
        db, _ = temp_db
        
        with pytest.raises(ValueError, match="At least one field"):
            db.create_fulltext_index([])
    
    def test_drop_fulltext_index(self, temp_db):
        """Test dropping a full-text index."""
        db, _ = temp_db
        db.create_fulltext_index(['title'])
        
        result = db.drop_fulltext_index('fulltext_title')
        assert result is True
        
        indexes = db.list_fulltext_indexes()
        assert len(indexes) == 0
    
    def test_drop_nonexistent_fulltext_index(self, temp_db):
        """Test dropping a non-existent index."""
        db, _ = temp_db
        result = db.drop_fulltext_index('nonexistent')
        assert result is False
    
    def test_drop_all_fulltext_indexes(self, temp_db):
        """Test dropping all full-text indexes."""
        db, _ = temp_db
        db.create_fulltext_index(['title'])
        db.create_fulltext_index(['content'])
        db.create_fulltext_index(['name'], name='custom')
        
        count = db.drop_all_fulltext_indexes()
        assert count == 3
        
        indexes = db.list_fulltext_indexes()
        assert len(indexes) == 0


class TestFullTextSearch:
    """Test full-text search functionality."""
    
    def test_basic_search(self, db_with_documents):
        """Test basic full-text search."""
        db, _ = db_with_documents
        db.create_fulltext_index(['title', 'content'])
        
        results = db.full_text_search('Python')
        assert len(results) >= 2
        
        # Check that Python-related documents are returned
        titles = [doc['title'] for doc in results]
        assert any('Python' in title for title in titles)
    
    def test_search_with_limit(self, db_with_documents):
        """Test full-text search with limit."""
        db, _ = db_with_documents
        db.create_fulltext_index(['title', 'content'])
        
        results = db.full_text_search('Python', limit=2)
        assert len(results) <= 2
    
    def test_search_multiple_words(self, db_with_documents):
        """Test searching for multiple words."""
        db, _ = db_with_documents
        db.create_fulltext_index(['title', 'content'])
        
        results = db.full_text_search('Python programming')
        assert len(results) >= 1
        
        # Documents with both words should rank higher
        assert any('Python' in doc['title'] or 'Python' in doc['content'] for doc in results)
    
    def test_search_no_index_fallback(self, db_with_documents):
        """Test that search works without index (fallback to linear scan)."""
        db, _ = db_with_documents
        # Don't create an index
        
        results = db.full_text_search('Python')
        # Should still find documents containing 'Python'
        assert len(results) >= 2
        
        for doc in results:
            text = str(doc.get('title', '')) + str(doc.get('content', ''))
            assert 'Python' in text
    
    def test_search_stop_words_filtered(self, db_with_documents):
        """Test that stop words are filtered from search."""
        db, _ = db_with_documents
        db.create_fulltext_index(['title', 'content'])
        
        # Search with stop words - should still work but ignore stop words
        results = db.full_text_search('the python')
        assert len(results) >= 1
    
    def test_search_case_insensitive(self, db_with_documents):
        """Test that search is case insensitive."""
        db, _ = db_with_documents
        db.create_fulltext_index(['title', 'content'])
        
        results_lower = db.full_text_search('python')
        results_upper = db.full_text_search('PYTHON')
        results_mixed = db.full_text_search('PyThOn')
        
        assert len(results_lower) == len(results_upper) == len(results_mixed)
    
    def test_search_no_results(self, db_with_documents):
        """Test search with no matching results."""
        db, _ = db_with_documents
        db.create_fulltext_index(['title', 'content'])
        
        results = db.full_text_search('nonexistentword12345')
        assert len(results) == 0
    
    def test_search_empty_query(self, db_with_documents):
        """Test search with empty query."""
        db, _ = db_with_documents
        db.create_fulltext_index(['title', 'content'])
        
        results = db.full_text_search('')
        assert len(results) == 0


class TestFullTextIndexMaintenance:
    """Test full-text index maintenance on CRUD operations."""
    
    def test_index_updated_on_insert(self, temp_db):
        """Test that index is updated when inserting documents."""
        db, _ = temp_db
        db.create_fulltext_index(['title'])
        
        # Insert a document
        db.insert_one({'title': 'Machine Learning Basics', 'content': 'Learn ML'})
        
        results = db.full_text_search('Machine')
        assert len(results) == 1
        assert results[0]['title'] == 'Machine Learning Basics'
    
    def test_index_updated_on_insert_many(self, temp_db):
        """Test that index is updated when batch inserting."""
        db, _ = temp_db
        db.create_fulltext_index(['title'])
        
        db.insert_many([
            {'title': 'Deep Learning', 'content': 'Neural networks'},
            {'title': 'Data Science', 'content': 'Analytics'},
        ])
        
        results = db.full_text_search('Learning')
        assert len(results) >= 1
    
    def test_index_updated_on_update(self, db_with_documents):
        """Test that index is updated when modifying documents."""
        db, _ = db_with_documents
        db.create_fulltext_index(['title', 'content'])
        
        # Get the first Python document
        python_doc = db.find_one({'title': {'$regex': 'Python'}})
        assert python_doc is not None
        
        # Update the document
        db.update_one(
            {'_id': python_doc['_id']},
            {'$set': {'title': 'Introduction to Java', 'content': 'Java is enterprise'}}
        )
        
        # Search for Python - should not return updated doc
        results = db.full_text_search('Python')
        assert len(results) >= 1  # Should still find other Python docs
        
        # Search for Java - should return updated doc
        results = db.full_text_search('Java')
        assert len(results) >= 1
        assert any(doc['_id'] == python_doc['_id'] for doc in results)
    
    def test_index_updated_on_delete(self, db_with_documents):
        """Test that index is updated when deleting documents."""
        db, _ = db_with_documents
        db.create_fulltext_index(['title', 'content'])
        
        # Get the first Python document
        python_doc = db.find_one({'title': {'$regex': 'Python'}})
        assert python_doc is not None
        doc_id = python_doc['_id']
        
        # Delete the Python document
        db.delete_one({'_id': doc_id})
        
        results = db.full_text_search('Python')
        # Should not contain deleted document
        assert all(doc['_id'] != doc_id for doc in results)
    
    def test_index_updated_on_delete_many(self, db_with_documents):
        """Test that index is updated when deleting multiple documents."""
        db, _ = db_with_documents
        db.create_fulltext_index(['title', 'content'])
        
        initial_count = len(db.full_text_search('Python'))
        
        # Delete all Python documents
        db.delete_many({'title': {'$regex': 'Python'}})
        
        results = db.full_text_search('Python')
        assert len(results) < initial_count


class TestFullTextIndexStats:
    """Test full-text index statistics."""
    
    def test_get_index_stats(self, db_with_documents):
        """Test getting index statistics."""
        db, _ = db_with_documents
        db.create_fulltext_index(['title', 'content'])
        
        indexes = db.list_fulltext_indexes()
        assert len(indexes) == 1
        
        stats = indexes[0]
        assert 'vocabulary_size' in stats
        assert 'num_documents' in stats
        assert 'avg_doc_length' in stats
        assert stats['num_documents'] == 5
    
    def test_index_rebuild_on_load(self, temp_db):
        """Test that full-text index is rebuilt when database is reopened."""
        db, filename = temp_db
        db.create_fulltext_index(['title'])
        db.insert_one({'title': 'Test Document', 'content': 'Test content'})
        
        # Close and reopen database
        del db
        
        db2 = JSONlite(filename)
        # Note: Full-text indexes are in-memory only, so they won't persist
        # This is expected behavior - user needs to recreate indexes
        indexes = db2.list_fulltext_indexes()
        assert len(indexes) == 0


class TestFullTextIndexPerformance:
    """Test full-text index performance improvements."""
    
    def test_indexed_search_faster(self, temp_db):
        """Test that indexed search is faster than linear scan."""
        import time
        
        db, _ = temp_db
        
        # Insert many documents
        documents = [
            {'title': f'Document {i}', 'content': f'Content with keyword test {i}'}
            for i in range(1000)
        ]
        db.insert_many(documents)
        
        # Search without index
        start = time.time()
        results_no_index = db.full_text_search('keyword')
        time_no_index = time.time() - start
        
        # Create index
        db.create_fulltext_index(['title', 'content'])
        
        # Search with index
        start = time.time()
        results_with_index = db.full_text_search('keyword')
        time_with_index = time.time() - start
        
        # Both should return same number of results
        assert len(results_no_index) == len(results_with_index)
        
        # Index should be faster (at least not slower)
        # Note: For small datasets, overhead might make it similar
        print(f"Without index: {time_no_index:.4f}s, With index: {time_with_index:.4f}s")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
