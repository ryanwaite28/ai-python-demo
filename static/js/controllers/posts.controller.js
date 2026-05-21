angular.module('blogApp').controller('PostsController', ['$scope', '$window', 'ApiService', function($scope, $window, ApiService) {
    $scope.posts = [];
    $scope.currentPost = null;
    $scope.replies = [];
    $scope.loading = false;
    $scope.error = null;
    $scope.page = 1;
    $scope.totalPages = 1;
    
    $scope.loadPosts = function() {
        $scope.loading = true;
        ApiService.posts.getAll({ page: $scope.page, limit: 20 })
            .then(function(response) {
                $scope.posts = response.data.posts;
                $scope.totalPages = response.data.pages;
                $scope.loading = false;
            })
            .catch(function(error) {
                $scope.error = 'Failed to load posts';
                $scope.loading = false;
            });
    };
    
    $scope.loadPost = function(postId) {
        $scope.loading = true;
        ApiService.posts.getById(postId)
            .then(function(response) {
                $scope.currentPost = response.data.post;
                $scope.replies = response.data.replies;
                $scope.loading = false;
            })
            .catch(function(error) {
                $scope.error = 'Failed to load post';
                $scope.loading = false;
            });
    };
    
    $scope.createPost = function(postData) {
        $scope.loading = true;
        $scope.error = null;
        
        ApiService.posts.create(postData)
            .then(function(response) {
                $scope.loading = false;
                $window.location.href = '/posts/' + response.data.post.id;
            })
            .catch(function(error) {
                $scope.error = error.data.error || 'Failed to create post';
                $scope.loading = false;
            });
    };
    
    $scope.updatePost = function(postId, postData) {
        $scope.loading = true;
        $scope.error = null;
        
        ApiService.posts.update(postId, postData)
            .then(function(response) {
                $scope.loading = false;
                $window.location.href = '/posts/' + postId;
            })
            .catch(function(error) {
                $scope.error = error.data.error || 'Failed to update post';
                $scope.loading = false;
            });
    };
    
    $scope.deletePost = function(postId) {
        if (!confirm('Are you sure you want to delete this post?')) {
            return;
        }
        
        ApiService.posts.delete(postId)
            .then(function() {
                $window.location.href = '/posts';
            })
            .catch(function(error) {
                $scope.error = 'Failed to delete post';
            });
    };
    
    $scope.savePost = function(postId) {
        ApiService.posts.save(postId)
            .then(function() {
                alert('Post saved!');
            })
            .catch(function(error) {
                $scope.error = 'Failed to save post';
            });
    };
    
    $scope.unsavePost = function(postId) {
        ApiService.posts.unsave(postId)
            .then(function() {
                alert('Post unsaved!');
            })
            .catch(function(error) {
                $scope.error = 'Failed to unsave post';
            });
    };
    
    $scope.addReply = function(postId, replyData) {
        ApiService.posts.addReply(postId, replyData)
            .then(function(response) {
                $scope.replies.push(response.data.reply);
                $scope.replyContent = '';
            })
            .catch(function(error) {
                $scope.error = 'Failed to add reply';
            });
    };
    
    $scope.nextPage = function() {
        if ($scope.page < $scope.totalPages) {
            $scope.page++;
            $scope.loadPosts();
        }
    };
    
    $scope.prevPage = function() {
        if ($scope.page > 1) {
            $scope.page--;
            $scope.loadPosts();
        }
    };
}]);
