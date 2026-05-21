angular.module('blogApp').controller('UsersController', ['$scope', 'ApiService', function($scope, ApiService) {
    $scope.user = null;
    $scope.userPosts = [];
    $scope.followers = [];
    $scope.following = [];
    $scope.savedPosts = [];
    $scope.loading = false;
    $scope.error = null;
    $scope.stats = {};
    
    $scope.loadUser = function(username) {
        $scope.loading = true;
        ApiService.users.getByUsername(username)
            .then(function(response) {
                $scope.user = response.data.user;
                $scope.stats = response.data.stats;
                $scope.loading = false;
            })
            .catch(function(error) {
                $scope.error = 'Failed to load user';
                $scope.loading = false;
            });
    };
    
    $scope.loadUserPosts = function(username) {
        ApiService.users.getUserPosts(username, { page: 1, limit: 20 })
            .then(function(response) {
                $scope.userPosts = response.data.posts;
            })
            .catch(function(error) {
                $scope.error = 'Failed to load user posts';
            });
    };
    
    $scope.followUser = function(username) {
        ApiService.users.follow(username)
            .then(function() {
                $scope.stats.followers_count++;
                alert('Now following ' + username);
            })
            .catch(function(error) {
                $scope.error = 'Failed to follow user';
            });
    };
    
    $scope.unfollowUser = function(username) {
        ApiService.users.unfollow(username)
            .then(function() {
                $scope.stats.followers_count--;
                alert('Unfollowed ' + username);
            })
            .catch(function(error) {
                $scope.error = 'Failed to unfollow user';
            });
    };
    
    $scope.loadFollowers = function(username) {
        ApiService.users.getFollowers(username)
            .then(function(response) {
                $scope.followers = response.data.followers;
            });
    };
    
    $scope.loadFollowing = function(username) {
        ApiService.users.getFollowing(username)
            .then(function(response) {
                $scope.following = response.data.following;
            });
    };
    
    $scope.loadSavedPosts = function() {
        $scope.loading = true;
        ApiService.users.getSavedPosts()
            .then(function(response) {
                $scope.savedPosts = response.data.posts;
                $scope.loading = false;
            })
            .catch(function(error) {
                $scope.error = 'Failed to load saved posts';
                $scope.loading = false;
            });
    };
}]);
