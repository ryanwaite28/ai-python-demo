angular.module('blogApp').controller('SettingsController', ['$scope', 'ApiService', function($scope, ApiService) {
    $scope.profile = {};
    $scope.passwordData = {};
    $scope.favoriteTags = [];
    $scope.loading = false;
    $scope.error = null;
    $scope.success = null;
    
    $scope.loadProfile = function() {
        ApiService.auth.getCurrentUser()
            .then(function(response) {
                $scope.profile = response.data.user;
            })
            .catch(function(error) {
                $scope.error = 'Failed to load profile';
            });
        
        ApiService.tags.getFavorites()
            .then(function(response) {
                $scope.favoriteTags = response.data.tags;
            });
    };
    
    $scope.updateProfile = function() {
        $scope.loading = true;
        $scope.error = null;
        $scope.success = null;
        
        setTimeout(function() {
            $scope.$apply(function() {
                $scope.loading = false;
                $scope.success = 'Profile updated successfully! (Note: Update API endpoint needed)';
            });
        }, 1000);
    };
    
    $scope.changePassword = function() {
        if ($scope.passwordData.new_password !== $scope.passwordData.confirm_password) {
            $scope.error = 'Passwords do not match';
            return;
        }
        
        $scope.loading = true;
        $scope.error = null;
        $scope.success = null;
        
        setTimeout(function() {
            $scope.$apply(function() {
                $scope.loading = false;
                $scope.success = 'Password changed successfully! (Note: Change password API endpoint needed)';
                $scope.passwordData = {};
            });
        }, 1000);
    };
    
    $scope.loadProfile();
}]);
