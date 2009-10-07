// Copyright 2009 FriendFeed
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may
// not use this file except in compliance with the License. You may obtain
// a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations
// under the License.


Date.prototype.getDiff = function(dt) {

    var m1 = this.valueOf();
    var m2 = dt.valueOf();
    
    var diff = {};
    diff.milliseconds = (m2 > m1) ? m2 - m1 : m1 - m2;
    diff.seconds = diff.milliseconds / 1000;

    diff.minutes = diff.seconds / 60; 
    diff.hours =  diff.minutes / 60;
    diff.days =  diff.hours / 24;
    diff.weeks =  diff.days / 7;
    diff.months =  diff.weeks / 4;
    
    return diff;    

}

Date.prototype.getDiffFormat = function(dt) {
    var diff = this.getDiff(dt);
    if (diff.hours < 24) {
        if (diff.minutes < 60) {
            if (diff.minutes < 1) {
                if (diff.seconds < 1) {
                    return  "1 second ago";
                } else { 
                    return  Math.floor(diff.seconds) + " seconds ago";
                }
            } else {
                var s = (Math.floor(diff.minutes) == 1) ? " minute ago" : " minutes ago"
                return Math.floor(diff.minutes) + s;
            }        
        } else {
            var s = (Math.floor(diff.hours) == 1) ? " hour ago" : " hours ago"
            return Math.floor(diff.hours) + s;
        }
    } else if (diff.weeks > 0 && diff.weeks < 1) {
        var s = (Math.floor(diff.days) == 1) ? " day ago" : " days ago"
        return Math.floor(diff.days) + s;
    } else if (diff.weeks >= 1 && diff.weeks < 5) {
        var s = (Math.floor(diff.weeks) == 1) ? " week ago" : " weeks ago"
        return Math.floor(diff.weeks) + s;
    } else {
        var s = (Math.floor(diff.months) == 1) ? " month ago" : " months ago"
        return Math.floor(diff.months) + s;        
    }
}

function getCookie(name) {
    var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
    return r ? r[1] : undefined;
}

function text_counter(txt_id, cnt_id) {
	var txt_el = $('#' + txt_id);
    $('#' + cnt_id).html(txt_el.val().length + ' characters');
}

jQuery.postJSON = function(url, args, callback) {
    args._xsrf = getCookie("_xsrf");
  args.client_id = CLIENT_ID;
    $.ajax({url: url, data: $.param(args), dataType: "text", type: "POST",
	    success: function(response) {
	//if (callback) callback(eval("(" + response + ")"));
    }, error: function(response) {
	console.log("ERROR:", response)
    }});
};

jQuery.fn.formToDict = function() {
    var fields = this.serializeArray();
    var json = {}
    for (var i = 0; i < fields.length; i++) {
	json[fields[i].name] = fields[i].value;
    }
    if (json.next) delete json.next;
    return json;
};

jQuery.fn.disable = function() {
    this.enable(false);
    return this;
};

jQuery.fn.enable = function(opt_enable) {
    if (arguments.length && !opt_enable) {
        this.attr("disabled", "disabled");
    } else {
        this.removeAttr("disabled");
    }
    return this;
};

var TF = {
    sleep_time: 5000,
    
    status:function(){
        var status = $('#status').val()
        
        if (status.length > 0){
            var twitter = $('#status_twitter')
            if (twitter){
                if (twitter.attr('checked')) {
                    TF.twitter.status(status)
                }
            }
            var facebook = $('#status_facebook')
            if (facebook){
                if (facebook.attr('checked')) {
                    TF.facebook.status(status)
                }
            }
        } else {
            alert('missing status')
        }
    },
    clear_status:function(){
        $('#status').val() = ''
    },
    end:function(){}
}

TF.twitter = {
    chunks: 0,

    poll: function() {
    	var args = {"_xsrf": getCookie("_xsrf")};
    	$.ajax({
    	    url: "/a/twitter/timeline", 
    	    type: "POST", 
    	    dataType: "text",
    		data: $.param(args), 
    		success: this.poll_cb,
    		error: this.poll_error
    	});
    },
    poll_cb: function(response) {
        // console.log('on success', response)
        TF.twitter.insert(response)
        window.setTimeout(function(){TF.twitter.poll()}, TF.sleep_time);
        // window.setTimeout(TF.twitter.poll, 0);
    },
    poll_error: function(response) {
    	// updater.errorSleepTime *= 2;
        // console.log("Poll error; sleeping for", TF.sleep_time, "ms");
    	window.setTimeout(TF.twitter.poll, TF.sleep_time);
    },

    insert: function(response) {
        $('#twitter_poll_loading').hide()

        this.chunks += 1
        var chunk_id = 'twitter_chunk_' + this.chunks
        var a = []
        a.push('<div style="display:none; background:#fff" id="')
        a.push(chunk_id)
        a.push('">')
        a.push(response)
        a.push('</div>')
        $("#tweets").prepend(a.join(''))
        $('#' + chunk_id).slideDown(1000, function(){
            $(this).effect("highlight", {}, 3000);
        });
        $('#'+ chunk_id + ' > div.tweet > div.body > div.text').linkify();
        time.ago();
        this.reset_load_more()
    },
    
    reset_load_more:function(){
        $('#twitter_previous_hanlder').show()
        $('#twitter_previous_hanlder_loading').hide() 
    },

    show_load_more:function(){
        $('#twitter_previous_hanlder').hide()
        $('#twitter_previous_hanlder_loading').show() 
    },
    
    prev: function() {
        var tweets = $('.tweet')
        var max_id = ''
        if (tweets.length > 0) {
            this.show_load_more()
            max_id = tweets[tweets.length - 1].id.split('-')[1]
        	var args = {"_xsrf": getCookie("_xsrf"), "max_id": max_id};
        	$.ajax({
        	    url: "/a/twitter/timeline/previous", 
        	    type: "POST", 
        	    dataType: "text",
        		data: $.param(args), 
        		success: this.prev_cb,
        		error: this.prev_error
        	});
        }
    },
    prev_cb: function(response) {
        // console.log('on success', response)
        TF.twitter.chunks += 1
        var chunk_id = 'twitter_chunk_' + TF.twitter.chunks
        var a = []
        a.push('<div style="display:none; background:#fff" id="')
        a.push(chunk_id)
        a.push('">')
        a.push(response)
        a.push('</div>')
        $("#tweets").append(a.join(''))
        $('#' + chunk_id).slideDown(1000, function(){
            document.location.hash=this.id;
            $(this).effect("highlight", {}, 3000);
        });
        
        $('#'+ chunk_id + ' > div.tweet > div.body > div.text').linkify();
        time.ago();
        TF.twitter.reset_load_more()
    },
    prev_error: function(response) {
        TF.twitter.reset_load_more()
    },
    last_status:function(){
        var args = {"_xsrf": getCookie("_xsrf")};
        $.ajax({
             url: "/a/twitter/status/last", 
             type: "POST", 
             dataType: "text",
             data: $.param(args), 
             success: this.last_status_cb,
             error: this.last_status_error
        });
    },
    last_status_cb:function(response){
        $('#last_tweet').html(response)
        $("#last_tweet").linkify();
        time.ago();
    },    
    status: function(status) {
    	var args = {"_xsrf": getCookie("_xsrf"), "status": status};
    	$.ajax({
    	    url: "/a/twitter/status", 
    	    type: "POST", 
    	    dataType: "text",
    		data: $.param(args), 
    		success: this.status_cb,
    		error: this.status_error
    	});
    },
    status_cb:function(response){
        $("#last_tweet").html(response)
        $("#last_tweet").linkify();
        time.ago();
        TF.clear_status()

    },
    status_error:function(result){
        alert('there was an error saving twitter status')
    },
    end:function(){}
};

TF.facebook = {
    chunks: 0,
    
    poll: function() {
    	var args = {"_xsrf": getCookie("_xsrf")};
    	$.ajax({
    	    url: "/a/facebook/stream", 
    	    type: "POST", 
    	    dataType: "text",
    		data: $.param(args), 
    		success: this.poll_cb,
    		error: this.poll_error
    	});
    },
    poll_cb: function(response) {
        // console.log('on success', response)
        TF.facebook.insert(response)
        window.setTimeout(function(){TF.facebook.poll()}, TF.sleep_time);
    },
    poll_error: function(response) {
    	// updater.errorSleepTime *= 2;
        // console.log("Poll error; sleeping for", TF.sleep_time, "ms");
    	window.setTimeout(TF.facebook.poll, TF.sleep_time);
    },
    reset_load_more:function(){
        $('#facebook_previous_hanlder').show()
        $('#facebook_previous_hanlder_loading').hide() 
    },

    show_load_more:function(){
        $('#facebook_previous_hanlder').hide()
        $('#facebook_previous_hanlder_loading').show() 
    },
    
    insert: function(response) {
        $('#facebook_poll_loading').hide()
        this.chunks += 1
        var chunk_id = 'facebook_chunk_' + this.chunks
        var a = []
        a.push('<div style="display:none; background:#fff" id="')
        a.push(chunk_id)
        a.push('">')
        a.push(response)
        a.push('</div>')
        $("#posts").prepend(a.join(''))
        $('#' + chunk_id).slideDown(1000, function(){
            $(this).effect("highlight", {}, 3000);
        });
        $('#'+ chunk_id + ' > div.post > div.body > span.message').linkify();
        $('#'+ chunk_id + ' > div.post > div.body > div.comments > div.comment').linkify();        
        // time.ago();
        this.reset_load_more()
    },
    prev: function() {
        var posts = $('div.post')
        var end_time = ''
        if (posts.length > 0) {
            this.show_load_more()
            end_time = posts[posts.length - 1].title
            var args = {"_xsrf": getCookie("_xsrf"), "end_time": end_time};
            $.ajax({
                 url: "/a/facebook/timeline/previous", 
                 type: "POST", 
                 dataType: "text",
                 data: $.param(args), 
                 success: this.prev_cb,
                 error: this.prev_error
            });
        }
    },
    prev_cb: function(response) {
        // console.log('on success', response)
        TF.facebook.chunks += 1
        var chunk_id = 'facebook_chunk_' + TF.facebook.chunks
        var a = []
        a.push('<div style="display:none; background:#fff" id="')
        a.push(chunk_id)
        a.push('">')
        a.push(response)
        a.push('</div>')
        $("#posts").append(a.join(''))
        $('#' + chunk_id).slideDown(1000, function(){
            document.location.hash=this.id;
            $(this).effect("highlight", {}, 3000);
        });
        $('#'+ chunk_id + ' > div.post > div.body > span.message').linkify();
        $('#'+ chunk_id + ' > div.post > div.body > div.comments > div.comment').linkify();
        TF.facebook.reset_load_more()
    },
    prev_error: function(response) {
        TF.facebook.reset_load_more()
    },
    last_status:function(){
        var args = {"_xsrf": getCookie("_xsrf")};
        $.ajax({
             url: "/a/facebook/status/last", 
             type: "POST", 
             dataType: "text",
             data: $.param(args), 
             success: this.last_status_cb,
             error: this.last_status_error
        });
    },
    last_status_cb:function(response){
        $('#last_post').html(response)
        $("#last_post").linkify();
    },
    last_status_error:function(){},
    status: function(status) {
    	var args = {"_xsrf": getCookie("_xsrf"), "status": status};
    	$.ajax({
    	    url: "/a/facebook/status", 
    	    type: "POST", 
    	    dataType: "text",
    		data: $.param(args), 
    		success: this.status_cb,
    		error: this.status_error
    	});
    },
    status_cb:function(response){
        TF.facebook.last_status()
        TF.clear_status()
    },
    status_error:function(response){
        alert('there was an error saving facebook status')
    },
    end:function(){}
}

var time = {
    ago:function(){
        var date; 
        var dates = $('.time_lapse');
        var out = []
        this.now = new Date()
        this.now.addMilliseconds( (this.now.getTimezoneOffset() * 60 ) * 1000)
        // alert(dates.length)
        for(var i=0;i<dates.length; i++){
            date = dates[i];
            date.innerHTML = Date.parse(date.title).getDiffFormat(this.now) // + ' ('+ date.title +'/'+ this.now.toString() +') ';
            // var dt = Date.parse(date.title)
            // out.push(date.title  + "<br />" + )
            // this.format_date(date);
         }
         // document.getElementById('log').innerHTML = out.join("<hr />")
    },
    format_date:function(date){
        // now.getTimezoneOffset()
        date.innerHTML = Date.parse(date.title) + ' ('+ date.title +'/'+ this.now.toString() +') ' //.getDiffFormat(this.now) + ' ('+ date.title +'/'+ this.now.toString() +') ';
    },
    end:function(){}
};


// 
// Define: Linkify plugin
(function($){

  var url1 = /(^|&lt;|\s)(www\..+?\..+?)(\s|&gt;|$)/g,
      url2 = /(^|&lt;|\s)(((https?|ftp):\/\/|mailto:).+?)(\s|&gt;|$)/g,
      url3 = /(@)(.+?|$)((:)|\s)/g,
      url4 = /(\#)(.+?|$)(\s)/g


      linkifyThis = function () {
        var childNodes = this.childNodes,
            i = childNodes.length;
        while(i--)
        {
          var n = childNodes[i];
          if (n.nodeType == 3) {
            var html = $.trim(n.nodeValue);
            if (html)
            {
              html = html.replace(/&/g, '&amp;')
                         .replace(/</g, '&lt;')
                         .replace(/>/g, '&gt;')
                         .replace(url1, '$1 <a href="http://$2" target="_blank">$2</a> $3')
                         .replace(url2, '$1 <a href="$2" target="_blank">$2</a> $5')
                         .replace(url3, '$1<a href="http://twitter.com/$2">$2</a>&nbsp;$3')
                         .replace(url4, '$1<a href="http://search.twitter.com/search?q=$2">$2</a> $3')
                         
              $(n).after(html).remove();
            }
          }
          else if (n.nodeType == 1  &&  !/^(a|button|textarea)$/i.test(n.tagName)) {
            linkifyThis.call(n);
          }
        }
      };

  $.fn.linkify = function () {
    return this.each(linkifyThis);
  };

})(jQuery); 
 
$(document).ready(function() {
    //     if (!window.console) window.console = {};
    //     if (!window.console.log) window.console.log = function() {};
    // 
    //     $("#messageform").live("submit", function() {
    // newMessage($(this));
    // return false;
    //     });
    //     $("#messageform").live("keypress", function(e) {
    // if (e.keyCode == 13) {
    //     newMessage($(this));
    //     return false;
    // }
    //     });
    //     $("#message").select();
    //TF.twitter.poll();
    //time.ago();
}); 