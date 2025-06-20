/**
 * 后台登录
 * Copyright (c) 2020 smanor
 * QQ:57223165
 */
$(function() {
    layer.config({skin: 'layui-layer-hui'});
    if (getParam("kickout") == 1) {
        layer.msg('您已在别处登录，请您修改密码或重新登录', {offset: '10px'});
    }
	$('#imgcode').click(function() {
		var url = ctx + "captchaImage?type=" + captchaType + "&s=" + Math.random();
		$(this).attr("src", url);
	});

	$("input[type=text], input[type=password]").focus(function(){
	    $(this).parent().addClass('focus').removeClass('error');
    }).blur(function () {
        $(this).parent().removeClass('focus')
    })

    $('#submitBtn').click(function () {
        if(!$(this).hasClass('loading')){
            login();
        }
    })
});

function login() {
	let username = $("input[name='username']").val().toString().replace(/(^\s*)|(\s*$)|\r|\n/g, "")
        ,password = $("input[name='password']").val().toString().replace(/(^\s*)|(\s*$)|\r|\n/g, "")
        ,validateCode = $("input[name='validateCode']").val()
        ,rememberMe = $("input[name='rememberme']").is(':checked')
        ,userValid = true, pwdValid = true, codeVaild = true;

    if(username === '' || username.length === 0){
        userValid = false;
        $('input[name=username]').parent().addClass('error');
    }

    if(password === '' || password.length === 0){
        pwdValid = false;
        $('input[name=password]').parent().addClass('error');
    }

    if($("input[name='validateCode']").length > 0 && validateCode.length !== 4){
        codeVaild = false;
        $('input[name=validateCode]').parent().addClass('error');
    }

    if(userValid && pwdValid && codeVaild){
        $('#submitBtn').addClass('loading');
        $.ajax({
            type: "post",
            url: ctx + "login",
            data: {
                "username": username,
                "password": $.md5(password),
                "validateCode": validateCode,
                "rememberMe": rememberMe
            },
            success: function(r) {
                $('#submitBtn').removeClass('loading');
                if (r.code === 0) {
                    location.href = ctx + 'index';
                } else {
                    $('#imgcode').click();
                    $(".code").val("");
                    layer.msg(r.msg, {time: 2000});
                }
            }
        });
    }
}
function getParam(paramName) {
    let reg = new RegExp("(^|&)" + paramName + "=([^&]*)(&|$)"),
        r = window.location.search.substr(1).match(reg);
    if (r != null){ return decodeURI(r[2]);} else{ return null;}
}