angular.module('blogApp').factory('ApiService', ['$http', function($http) {
    const baseUrl = '/api';
    
    return {
        auth: {
            signup: function(data) {
                return $http.post(baseUrl + '/auth/signup', data);
            },
            login: function(data) {
                return $http.post(baseUrl + '/auth/login', data);
            },
            logout: function() {
                return $http.post(baseUrl + '/auth/logout');
            },
            getCurrentUser: function() {
                return $http.get(baseUrl + '/auth/me');
            }
        },
        
        posts: {
            getAll: function(params) {
                return $http.get(baseUrl + '/posts', { params: params });
            },
            getById: function(id) {
                return $http.get(baseUrl + '/posts/' + id);
            },
            create: function(data) {
                return $http.post(baseUrl + '/posts', data);
            },
            update: function(id, data) {
                return $http.put(baseUrl + '/posts/' + id, data);
            },
            delete: function(id) {
                return $http.delete(baseUrl + '/posts/' + id);
            },
            save: function(id) {
                return $http.post(baseUrl + '/posts/' + id + '/save');
            },
            unsave: function(id) {
                return $http.delete(baseUrl + '/posts/' + id + '/save');
            },
            addReply: function(id, data) {
                return $http.post(baseUrl + '/posts/' + id + '/replies', data);
            }
        },
        
        users: {
            getByUsername: function(username) {
                return $http.get(baseUrl + '/users/' + username);
            },
            getUserPosts: function(username, params) {
                return $http.get(baseUrl + '/users/' + username + '/posts', { params: params });
            },
            follow: function(username) {
                return $http.post(baseUrl + '/users/' + username + '/follow');
            },
            unfollow: function(username) {
                return $http.delete(baseUrl + '/users/' + username + '/follow');
            },
            getFollowers: function(username) {
                return $http.get(baseUrl + '/users/' + username + '/followers');
            },
            getFollowing: function(username) {
                return $http.get(baseUrl + '/users/' + username + '/following');
            },
            getSavedPosts: function() {
                return $http.get(baseUrl + '/users/me/saved');
            }
        },
        
        messages: {
            getInbox: function(params) {
                return $http.get(baseUrl + '/messages', { params: params });
            },
            getSent: function() {
                return $http.get(baseUrl + '/messages/sent');
            },
            getById: function(id) {
                return $http.get(baseUrl + '/messages/' + id);
            },
            send: function(data) {
                return $http.post(baseUrl + '/messages', data);
            },
            delete: function(id) {
                return $http.delete(baseUrl + '/messages/' + id);
            },
            markAsRead: function(id) {
                return $http.put(baseUrl + '/messages/' + id + '/read');
            }
        },
        
        tags: {
            getAll: function(params) {
                return $http.get(baseUrl + '/tags', { params: params });
            },
            getPostsByTag: function(tagName, params) {
                return $http.get(baseUrl + '/tags/' + tagName + '/posts', { params: params });
            },
            favorite: function(tagId) {
                return $http.post(baseUrl + '/tags/' + tagId + '/favorite');
            },
            unfavorite: function(tagId) {
                return $http.delete(baseUrl + '/tags/' + tagId + '/favorite');
            },
            getFavorites: function() {
                return $http.get(baseUrl + '/tags/favorites');
            },
            search: function(params) {
                return $http.get(baseUrl + '/tags/search', { params: params });
            }
        },
        
        feed: {
            get: function(params) {
                return $http.get(baseUrl + '/feed', { params: params });
            }
        }
    };
}]);
