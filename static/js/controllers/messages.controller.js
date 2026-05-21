angular.module('blogApp').controller('MessagesController', ['$scope', '$window', 'ApiService', function($scope, $window, ApiService) {
    $scope.messages = [];
    $scope.currentMessage = null;
    $scope.loading = false;
    $scope.error = null;
    $scope.unreadCount = 0;
    
    $scope.loadInbox = function() {
        $scope.loading = true;
        ApiService.messages.getInbox({ page: 1, limit: 50 })
            .then(function(response) {
                $scope.messages = response.data.messages;
                $scope.unreadCount = response.data.unread_count;
                $scope.loading = false;
            })
            .catch(function(error) {
                $scope.error = 'Failed to load messages';
                $scope.loading = false;
            });
    };
    
    $scope.loadSent = function() {
        $scope.loading = true;
        ApiService.messages.getSent()
            .then(function(response) {
                $scope.messages = response.data.messages;
                $scope.loading = false;
            })
            .catch(function(error) {
                $scope.error = 'Failed to load sent messages';
                $scope.loading = false;
            });
    };
    
    $scope.sendMessage = function(messageData) {
        $scope.loading = true;
        $scope.error = null;
        
        ApiService.messages.send(messageData)
            .then(function() {
                $scope.loading = false;
                $window.location.href = '/messages';
            })
            .catch(function(error) {
                $scope.error = error.data.error || 'Failed to send message';
                $scope.loading = false;
            });
    };
    
    $scope.deleteMessage = function(messageId) {
        if (!confirm('Are you sure you want to delete this message?')) {
            return;
        }
        
        ApiService.messages.delete(messageId)
            .then(function() {
                $scope.loadInbox();
            })
            .catch(function(error) {
                $scope.error = 'Failed to delete message';
            });
    };
    
    $scope.markAsRead = function(messageId) {
        ApiService.messages.markAsRead(messageId)
            .then(function() {
                var message = $scope.messages.find(function(m) { return m.id === messageId; });
                if (message) {
                    message.is_read = true;
                    $scope.unreadCount--;
                }
            });
    };
}]);
