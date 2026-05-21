angular.module('blogApp').controller('AuthController', ['$scope', '$window', 'ApiService', function($scope, $window, ApiService) {
    $scope.signupData = {};
    $scope.loginData = {};
    $scope.error = null;
    $scope.loading = false;
    
    $scope.signup = function() {
        $scope.error = null;
        $scope.loading = true;
        
        ApiService.auth.signup($scope.signupData)
            .then(function(response) {
                $scope.loading = false;
                $window.location.href = '/';
            })
            .catch(function(error) {
                $scope.loading = false;
                $scope.error = error.data.error || 'Signup failed';
            });
    };
    
    $scope.login = function() {
        $scope.error = null;
        $scope.loading = true;
        
        ApiService.auth.login($scope.loginData)
            .then(function(response) {
                $scope.loading = false;
                $window.location.href = '/';
            })
            .catch(function(error) {
                $scope.loading = false;
                $scope.error = error.data.error || 'Login failed';
            });
    };
    
    $scope.logout = function() {
        ApiService.auth.logout()
            .then(function() {
                $window.location.href = '/login';
            });
    };
}]);
