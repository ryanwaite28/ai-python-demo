angular.module('blogApp').controller('HomeController', ['$scope', 'ApiService', function($scope, ApiService) {
    $scope.stats = {};
    $scope.recentPosts = [];
    $scope.unreadMessages = 0;
    $scope.loading = false;
    
    $scope.loadUserStats = function() {
        ApiService.auth.getCurrentUser()
            .then(function(response) {
                var username = response.data.user.username;
                
                ApiService.users.getByUsername(username)
                    .then(function(userResponse) {
                        $scope.stats = userResponse.data.stats;
                    });
                
                ApiService.users.getUserPosts(username, { page: 1, limit: 5 })
                    .then(function(postsResponse) {
                        $scope.recentPosts = postsResponse.data.posts;
                    });
                
                ApiService.messages.getInbox({ page: 1, limit: 1 })
                    .then(function(messagesResponse) {
                        $scope.unreadMessages = messagesResponse.data.unread_count;
                    });
            })
            .catch(function(error) {
                console.error('Error loading user data:', error);
            });
    };
    
    $scope.loadUserStats();
}]);
