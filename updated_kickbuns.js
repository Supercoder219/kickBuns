(function(window) {
    var JSONP=(function(){
        var counter=0,head,query,key,window=this;
        function load(url){
            var script=document.createElement('script'),done=false;
            script.src=url;script.async=true;
            script.onload=script.onreadystatechange=function(){
                if(!done&&(!this.readyState||this.readyState==="loaded"||this.readyState==="complete")){
                    done=true;script.onload=script.onreadystatechange=null;
                    if(script&&script.parentNode){
                        script.parentNode.removeChild(script);
                    }
                }
            };
            if(!head){
                head=document.getElementsByTagName('head')[0];
                if(!head) head=document.body;
            }
            head.appendChild(script);
        }
        function jsonp(url,params,callback){
            query="?";params=params||{};
            for(key in params){
                if(params.hasOwnProperty(key)){
                    query+=encodeURIComponent(key)+"="+encodeURIComponent(params[key])+"&";
                }
            }
            var jsonp="json"+(++counter);
            window[jsonp]=function(data){
                callback(data);
                try{
                    delete window[jsonp];
                } catch(e){}
                window[jsonp]=null;
            };
            load(url+query+"callback="+jsonp);
            return jsonp;
        }
        return {get:jsonp};
    }());

    var CORS={request:function(url,params,callback){
        if(this.calledByExtension()){
            this._callbacks[this._callbackId++]=callback;
            window.postMessage(JSON.stringify({from:"kickBunsapp-page",url:url,type:"callApi",params:params}),"*");
            return;
        }
        params=params||{};var query="?";
        for(key in params){
            if(params.hasOwnProperty(key)){
                query+=encodeURIComponent(key)+"="+encodeURIComponent(params[key])+"&";
                }
            }
            var xhr=new XMLHttpRequest();
            xhr.onreadystatechange=function(){
                if(xhr.readyState==4){
                    callback(JSON.parse(xhr.responseText));
                }
            }
            xhr.open("GET",url+query);
            xhr.withCredentials=true;
            xhr.setRequestHeader("Content-Type","application/json");
            xhr.send();
        },
        calledByExtension:function(){
            return!!document.getElementById("kickBuns-has-been-initialized-yes-yes-yes");
        },
        _callbacks:{},
        _callbackId:0
    }

    if(CORS.calledByExtension()){
        window.addEventListener("message",function(e){
            var messageData;
            try{
                messageData=JSON.parse(e.data);
            } catch(e){ return; }
            if(messageData.from==="kickBunsapp-extension"&&messageData.sanityCheck==="kickBunsapp-extension-version1"){
                var message=messageData.payload;
                if(message.type==="response"){
                    CORS._callbacks[message.requestId](message.body);
                    delete CORS._callbacks[message.requestId];
                } else if(message.type==="destroy"){
                    window.KICKBunsGAME.destroy();
                }
            }
        },false);
    }

    function getGlobalNamespace(){
        return window&&window.INSTALL_SCOPE?window.INSTALL_SCOPE:window;
    }

    var ClBuns=function(methods){
        var ret=function(){
            if(ret.$prototyping)return this;
            if(typeof this.initialize=='function') return this.initialize.apply(this,arguments);
        };
        if(methods.Extends){
            ret.parent=methods.Extends;
            methods.Extends.$prototyping=true;
            ret.prototype=new methods.Extends;
            methods.Extends.$prototyping=false;
        }
        for(var key in methods)
            if(methods.hasOwnProperty(key))
                ret.prototype[key]=methods[key];
        return ret;
    };

    if(typeof exports!='undefined')
        exports.ClBuns=ClBuns;

    var Vector=new ClBuns({
        initialize:function(x,y){
            if(typeof x=='object'){
                this.x=x.x;
                this.y=x.y;
            } else {
                this.x=x;
                this.y=y;
            }
        },
        cp:function(){
            return new Vector(this.x,this.y);
        },
        mul:function(factor){
            this.x*=factor;
            this.y*=factor;
            return this;
        },
        mulNew:function(factor){
            return new Vector(this.x*factor,this.y*factor);
        },
        div:function(factor){
            this.x/=factor;
            this.y/=factor;
            return this;
        },
        divNew:function(factor){
            return new Vector(this.x/factor,this.y/factor);
        },
        add:function(vec){
            this.x+=vec.x;
            this.y+=vec.y;
            return this;
        },
        addNew:function(vec){
            return new Vector(this.x+vec.x,this.y+vec.y);
        },
        sub:function(vec){
            this.x-=vec.x;
            this.y-=vec.y;
            return this;
        },
        subNew:function(vec){
            return new Vector(this.x-vec.x,this.y-vec.y);
        },
        rotate:function(angle){
            var x=this.x,y=this.y;
            this.x=x*Math.cos(angle)-Math.sin(angle)*y;
            this.y=x*Math.sin(angle)+Math.cos(angle)*y;
            return this;
        },
        rotateNew:function(angle){
            return this.cp().rotate(angle);
        },
        setAngle:function(angle){
            var l=this.len();
            this.x=Math.cos(angle)*l;
            this.y=Math.sin(angle)*l;
            return this;
        },
        setAngleNew:function(angle){
            return this.cp().setAngle(angle);
        },
        setLength:function(length){
            var l=this.len();
            if(l)this.mul(length/l);
            else this.x=this.y=length;
            return this;
        },
        setLengthNew:function(length){
            return this.cp().setLength(length);
        },
        normalize:function(){
            var l=this.len();
            if(l==0) return this;
            this.x/=l;
            this.y/=l;
            return this;
        },
        normalizeNew:function(){
            return this.cp().normalize();
        },
        angle:function(){
            return Math.atan2(this.y,this.x);
        },
        collidesWith:function(rect){
            return this.x>rect.x&&this.y>rect.y&&this.x<rect.x+rect.width&&this.y<rect.y+rect.height;
        },
        len:function(){
            var l=Math.sqrt(this.x*this.x+this.y*this.y);
            if(l<0.005&&l>-0.005)return 0;
            return l;
        },
        is:function(test){
            return typeof test=='object'&&this.x==test.x&&this.y==test.y;
        },
        dot:function(v2){
            return this.x*v2.x+this.y*v2.y;
        },
        inTriangle:function(a,b,c){
            var v0=c.subNew(a);
            var v1=b.subNew(a);
            var v2=p.subNew(a);
            var dot00=v0.dot(v0);
            var dot01=v0.dot(v1);
            var dot02=v0.dot(v2);
            var dot11=v1.dot(v1);
            var dot12=v1.dot(v2);
            var invDenom=1/(dot00*dot11-dot01*dot01);
            var u=(dot11*dot02-dot01*dot12)*invDenom;
            var v=(dot00*dot12-dot01*dot02)*invDenom;
            return(u>0)&&(v>0)&&(u+v<1);
        },
        distanceFrom:function(vec){
            return Math.sqrt(Math.pow((this.x-vec.x),2),Math.pow(this.y-vec.y),2);
        },
        toString:function(){
            return'[Vector('+this.x+', '+this.y+') angle: '+this.angle()+', length: '+this.len()+']';
        }
    });

    if(typeof exports!='undefined')
        exports.Vector=Vector;

    var Rect=new ClBuns({
        initialize:function(x,y,w,h){
            this.pos=new Vector(x,y);
            this.size={width:w,height:h};
        },
        hasPoint:function(point){
            return point.x>this.getLeft()&&point.x<this.getRight()&&point.y>this.getTop()&&point.y<this.getBottom();
        },
        setLeft:function(left){
            this.pos.x=left+this.size.width/2;
        },
        setTop:function(top){
            this.pos.y=top+this.size.height/2;
        },
        getLeft:function(){
            return this.pos.x-this.size.width/2;
        },
        getTop:function(){
            return this.pos.y-this.size.height/2;
        },
        getRight:function(){
            return this.pos.x+this.size.width/2;
        },
        getBottom:function(){
            return this.pos.y+this.size.height/2;
        },
        cp:function(){
            return new Rect(this.pos.x,this.pos.y,this.size.width,this.size.height);
        }
    });

    if(typeof exports!='undefined')
        exports.Rect=Rect;

    var Fx=new ClBuns({
        initialize:function(){
            this.listeners=[];
            this.tweens={};
            this.running={};
        },
        addListener:function(listener){
            this.listeners.push(listener);
        },
        add:function(key,props){
            props=props||{};
            props.duration=props.duration||500;
            props.transition=props.transition||Tween.Linear;
            props.repeats=typeof props.repeats=='undefined'?false:props.repeats;
            if(!props.tweens){
                var start=props.start||0;
                var end=typeof props.end=='undefined'?1:props.end;
                props.tweens=[[start,end]];
            }
            this.tweens[key]=props;
        },
        update:function(time){
            time=typeof time==='number'?time:now();
            for(var key in this.tweens)
                if(this.tweens.hasOwnProperty(key)){
                    if(!this.running[key]){
                        this.tweenStart(key,time);
                        continue;
                    }
                    var tween=this.tweens[key];
                    var tdelta=time-this.running[key].startTime;
                    if(tdelta>tween.duration){
                        this.tweenFinished(tween,key);
                        continue;
                    }
                    var delta=tween.transition(tdelta/tween.duration);
                    var changes=[];
                    for(var i=0,t;t=tween.tweens[i];i++){
                        var x=delta*(t[1]-t[0])+t[0];
                        changes.push(x);
                    }
                    this.fire(key,changes,delta);
                }
        },
        tweenStart:function(key,time){
            this.running[key]={startTime:time};
            var values=[];
            for(var i=0,tween;tween=this.tweens[key].tweens[i];i++)
                values.push(tween[0]);
            this.fire(key,values,0);
        },
        tweenFinished:function(tween,key){
            var values=[];
            for(var i=0,t;t=tween.tweens[i];i++)
                values.push(t[1]);
            this.fire(key,values,1);
            if(!tween.repeats){
                delete this.running[key];
                delete this.tweens[key];
                return;
            }
        },
        fire:function(key,values,delta){
            for(var i=0,listener;listener=this.listeners[i];i++)
                listener(key,values,delta);
        }
    });

    if(typeof exports!='undefined')
        exports.Fx=Fx;

    // Embed CSS
    var css = `
    @import url(https://fonts.googleapis.com/css?family=Orbitron:400,500,700,900);

    #kickBuns-menu {
        position: fixed;
        bottom: 0;
        right: 0;
        left: 0;
        width: 100%;
        font: 20px Arial;
        color: black;
        z-index: 1000000;
        text-align: right;
        background: white;
        -webkit-transition: bottom 200ms;
        -moz-transition: bottom 200ms;
        -o-transition: bottom 200ms;
        -ms-transition: bottom 200ms;
        transition: bottom 200ms;
        border-top: 5px solid #1a1a1a;
    }

    #kickBuns-menu.KICKBunshidden {
        bottom: -250px;
    }

    #kickBuns-pointstab {
        border-bottom: 0;
        width: 263px;
        height: 97px;
        position: absolute;
        top: -102px;
        right: 75px;
        font-size: 20px;
        text-align: left;
        background: #363636;
        background: -moz-linear-gradient(top,  #363636 0%, #1a1a1a 100%);
        background: -webkit-linear-gradient(top,  #363636 0%,#1a1a1a 100%);
        background: -o-linear-gradient(top,	 #363636 0%,#1a1a1a 100%);
        background: -ms-linear-gradient(top,  #363636 0%,#1a1a1a 100%);
        background: linear-gradient(top,  #363636 0%,#1a1a1a 100%);
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        border: 2px solid #1d1f21;
        border-bottom: none;
        -webkit-box-shadow: inset 0px 1px 1px 0px rgba(255, 255, 255, 0.3);
        box-shadow: inset 0px 1px 1px 0px rgba(255, 255, 255, 0.3);
        cursor: pointer;
        color: #fff;
    }

        #kickBuns-pointstab-wrapper {
            padding-top: 20px;
            padding-bottom: 10px;
        }

        #kickBuns-points {
            margin-top: 2px;
            font-family: orbitron, helvetica, arial, sans-serif;
            font-weight: 400;
            font-size: 21px;
            text-shadow: 0px 0px 2px #a4c4bc;
            margin: 0 0 5px 27px;
        }

        #kickBuns-esctoquit {
            font-size: 12px;
            color: #787878;
            margin-left: 27px;
        }

        #kickBuns-pointstab-menu {
            margin: 0;
            padding: 0;
            list-style: none;
            font-size: 12px;
            border-top: 1px solid #333333;
        }

            #kickBuns-pointstab-menu a,
            #kickBuns-pointstab-menu a:visited {
                color: #ffffff;
            }

    .KICKBunsNOMENU #kickBuns-pointstab-menu {
        display: none;
    }

        #kickBuns-pointstab-menu li {
            float: left;
            border-right: 1px solid #333 ;
        }

            #kickBuns-pointstab-menu .last-li {
                border: none;
            }

        #kickBuns-pointstab-menu a {
            padding: 0 16px;
            display: block;
            height: 27px;
            line-height: 27px;
            cursor: pointer;
        }

        #kickBuns-pointstab-menu li:hover {
            background: #121212;
        }

        #kickBuns-pointstab-menu li:hover a {
            text-decoration: none;
        }

        #kickBuns-pointstab a:hover {
            text-decoration: none !important;
        }

    #kickBuns-pointstab .kickBuns-like {
        width: 80px;
        display: block;
        position: absolute;
        right: 10px;
        top: 28px;
    }

    #kickBuns-profile-menu {
        height: 248px;
        background: #fff;
        bottom: 0px;
        left: 0px;
        right: 0px;
    }

    #kickBuns-bomb-menu,
    #kickBuns-weapons-menu {
        background: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAALYAAAAXCAYAAACmsLVPAAAACXBIWXMAAAsTAAALEwEAmpwYAAAKT2lDQ1BQaG90b3Nob3AgSUNDIHByb2ZpbGUAAHjanVNnVFPpFj333vRCS4iAlEtvUhUIIFJCi4AUkSYqIQkQSoghodkVUcERRUUEG8igiAOOjoCMFVEsDIoK2AfkIaKOg6OIisr74Xuja9a89+bN/rXXPues852zzwfACAyWSDNRNYAMqUIeEeCDx8TG4eQuQIEKJHAAEAizZCFz/SMBAPh+PDwrIsAHvgABeNMLCADATZvAMByH/w/qQplcAYCEAcB0kThLCIAUAEB6jkKmAEBGAYCdmCZTAKAEAGDLY2LjAFAtAGAnf+bTAICd+Jl7AQBblCEVAaCRACATZYhEAGg7AKzPVopFAFgwABRmS8Q5ANgtADBJV2ZIALC3AMDOEAuyAAgMA...);
        width: 0px;
        height: 69px;
        padding-left: 46px;
        position: absolute;
        top: 15px;
        right: 100%;
        margin-right: -1px;
        transition: width 400ms;
        overflow: hidden;
    }

        #kickBuns-bomb-menu:hover,
        #kickBuns-weapons-menu:hover {
            background-position: left center;
        }

        #kickBuns-bomb-menu:active,
        #kickBuns-weapons-menu:active {
            background-position: left bottom;
        }

        #kickBuns-bomb-menu {
            background-image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAALYAAAAXCAYAAACmsLVPAAAACXBIWXMAAAsTAAALEwEAmpwYAAAKT2lDQ1BQaG90b3Nob3AgSUNDIHByb2ZpbGUAAHjanVNnVFPpFj333vRCS4iAlEtvUhUIIFJCi4AUkSYqIQkQSoghodkVUcERRUUEG8igiAOOjoCMFVEsDIoK2AfkIaKOg6OIisr74Xuja9a89+bN/rXXPues852zzwfACAyWSDNRNYAMqUIeEeCDx8TG4eQuQIEKJHAAEAizZCFz/SMBAPh+PDwrIsAHvgABeNMLCADATZvAMByH/w/qQplcAYCEAcB0kThLCIAUAEB6jkKmAEBGAYCdmCZTAKAEAGDLY2LjAFAtAGAnf+bTAICd+Jl7AQBblCEVAaCRACATZYhEAGg7AKzPVopFAFgwABRmS8Q5ANgtADBJV2ZIALC3AMDOEAuyAAgMA...);
            background-size: contain;
            left: 100%;
            padding-left: 0;
            width: 46px;
        }

    #kickBuns-weapons-list {
        background: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAALYAAAAXCAYAAACmsLVPAAAACXBIWXMAAAsTAAALEwEAmpwYAAAKT2lDQ1BQaG90b3Nob3AgSUNDIHByb2ZpbGUAAHjanVNnVFPpFj333vRCS4iAlEtvUhUIIFJCi4AUkSYqIQkQSoghodkVUcERRUUEG8igiAOOjoCMFVEsDIoK2AfkIaKOg6OIisr74Xuja9a89+bN/rXXPues852zzwfACAyWSDNRNYAMqUIeEeCDx8TG4eQuQIEKJHAAEAizZCFz/SMBAPh+PDwrIsAHvgABeNMLCADATZvAMByH/w/qQplcAYCEAcB0kThLCIAUAEB6jkKmAEBGAYCdmCZTAKAEAGDLY2LjAFAtAGAnf+bTAICd+Jl7AQBblCEVAaCRACATZYhEAGg7AKzPVopFAFgwABRmS8Q5ANgtADBJV2ZIALC3AMDOEAuyAAgMA...);
        margin: 0;
        padding: 0;
        list-style: none;
        width: 1000px;
        height: 100%;
    }

        #kickBuns-weapons-list .kickBuns-weapon-item {
            float: left;
            width: 60px;
            margin: 1px 0;
            padding-top: 42px;
            padding-bottom: 2px;
            border-right: 1px solid rgba(255, 255, 255, 0.15);
            text-align: center;
            background-repeat: no-repeat;
            background-position: center 7px;
        }

        #kickBuns-weapons-list .kickBuns-weapon-item:hover {
            background-color: rgba(255, 255, 255, 0.1);
        }

        #kickBuns-weapons-list .kickBuns-weapon-item span {
            font-size: 12px;
            background: #222;
            color: #fff;
            border-radius: 3px;
            padding: 2px 4px;
        }

    #kickBuns-hello-sunshine {
        position: absolute;
        top: 22px;
        right: 264px;
        border: none;
        height: 90px;
        width: 511px;
    }

    #kickBuns-howto-image {
      position: fixed;
      top: 20px;
      left: 80px;
        background: rgba(141, 175, 167, 0.9) url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAALYAAAAXCAYAAACmsLVPAAAACXBIWXMAAAsTAAALEwEAmpwYAAAKT2lDQ1BQaG90b3Nob3AgSUNDIHByb2ZpbGUAAHjanVNnVFPpFj333vRCS4iAlEtvUhUIIFJCi4AUkSYqIQkQSoghodkVUcERRUUEG8igiAOOjoCMFVEsDIoK2AfkIaKOg6OIisr74Xuja9a89+bN/rXXPues852zzwfACAyWSDNRNYAMqUIeEeCDx8TG4eQuQIEKJHAAEAizZCFz/SMBAPh+PDwrIsAHvgABeNMLCADATZvAMByH/w/qQplcAYCEAcB0kThLCIAUAEB6jkKmAEBGAYCdmCZTAKAEAGDLY2LjAFAtAGAnf+bTAICd+Jl7AQBblCEVAaCRACATZYhEAGg7AKzPVopFAFgwABRmS8Q5ANgtADBJV2ZIALC3AMDOEAuyAAgMA...);
      width: 200px;
      height: 100px;
      border-radius: 4px;
      border-radius: 4px;
      box-shadow: inset 0px 1px 1px 0px rgba(0, 0, 0, 0.3), 0px 1px 0px 0px rgba(255, 255, 255, 0.5);
      z-index: 10000000;
      text-align: center;
      transition: top 0.3s;
    }

    #kickBuns-howto-image:before {
      content: "Play with:";
      font: bold 14px arial;
      font-family: orbitron, helvetica, arial, sans-serif;
      color: white;
      text-transform: uppercase;
      padding-top: 15px;
      display: block;
    }

    #kickBuns-howto-image.kickBuns-howto-invisible {
      top: -100px;
    }
    `;

    var style=document.createElement('style');
    style.type='text/css';
    style.appendChild(document.createTextNode(css));
    document.head.appendChild(style);
})(window);

