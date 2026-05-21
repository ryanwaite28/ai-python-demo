angular.module('blogApp', []).config(function($interpolateProvider, $locationProvider) {
    $interpolateProvider.startSymbol('((');
    $interpolateProvider.endSymbol('))');
    
    $locationProvider.html5Mode({
        enabled: false,
        requireBase: false
    });
});
