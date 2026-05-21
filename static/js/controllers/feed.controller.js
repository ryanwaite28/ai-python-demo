angular.module('blogApp').controller('FeedController', ['$scope', 'ApiService', function($scope, ApiService) {
    $scope.posts = [];
    $scope.loading = false;
    $scope.error = null;
    $scope.page = 1;
    $scope.basedOnTags = [];
    
    $scope.loadFeed = function() {
        $scope.loading = true;
        ApiService.feed.get({ page: $scope.page, limit: 20 })
            .then(function(response) {
                $scope.posts = response.data.posts;
                $scope.basedOnTags = response.data.based_on_tags;
                $scope.loading = false;
            })
            .catch(function(error) {
                $scope.error = 'Failed to load feed';
                $scope.loading = false;
            });
    };
    
    $scope.loadFeed();
}]);
