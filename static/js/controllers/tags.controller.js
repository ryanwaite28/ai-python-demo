angular.module('blogApp').controller('TagsController', ['$scope', 'ApiService', function($scope, ApiService) {
    $scope.tags = [];
    $scope.favoriteTags = [];
    $scope.searchResults = [];
    $scope.loading = false;
    $scope.error = null;
    
    $scope.loadTags = function(popular) {
        $scope.loading = true;
        var params = { popular: popular || false, limit: 50 };
        
        ApiService.tags.getAll(params)
            .then(function(response) {
                $scope.tags = response.data.tags;
                $scope.loading = false;
            })
            .catch(function(error) {
                $scope.error = 'Failed to load tags';
                $scope.loading = false;
            });
    };
    
    $scope.loadPostsByTag = function(tagName) {
        $scope.loading = true;
        ApiService.tags.getPostsByTag(tagName, { page: 1, limit: 20 })
            .then(function(response) {
                $scope.searchResults = response.data.posts;
                $scope.loading = false;
            })
            .catch(function(error) {
                $scope.error = 'Failed to load posts';
                $scope.loading = false;
            });
    };
    
    $scope.favoriteTag = function(tagId) {
        ApiService.tags.favorite(tagId)
            .then(function() {
                var tag = $scope.tags.find(function(t) { return t.id === tagId; });
                if (tag) {
                    tag.favorited = true;
                }
                alert('Tag favorited!');
            })
            .catch(function(error) {
                $scope.error = 'Failed to favorite tag';
            });
    };
    
    $scope.unfavoriteTag = function(tagId) {
        ApiService.tags.unfavorite(tagId)
            .then(function() {
                var tag = $scope.tags.find(function(t) { return t.id === tagId; });
                if (tag) {
                    tag.favorited = false;
                }
                alert('Tag unfavorited!');
            })
            .catch(function(error) {
                $scope.error = 'Failed to unfavorite tag';
            });
    };
    
    $scope.loadFavoriteTags = function() {
        ApiService.tags.getFavorites()
            .then(function(response) {
                $scope.favoriteTags = response.data.tags;
            });
    };
    
    $scope.searchByTags = function(tagsString, matchType) {
        $scope.loading = true;
        var params = {
            tags: tagsString,
            match: matchType || 'all',
            page: 1,
            limit: 20
        };
        
        ApiService.tags.search(params)
            .then(function(response) {
                $scope.searchResults = response.data.posts;
                $scope.loading = false;
            })
            .catch(function(error) {
                $scope.error = 'Failed to search posts';
                $scope.loading = false;
            });
    };
}]);
