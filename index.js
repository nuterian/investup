var express = require('express');
var app = express();
var fs = require('fs');

app.use(express.static('public'));
app.set('views', './views');
app.set('view engine', 'jade');

app.get('/', function (req, res) {
    res.render('index');
});

function score(a, keys) {
    var score = 0;

    a = a.toLowerCase();
    a = a.replace(/\W+/g, ' '); //Convert all non-word characters to spaces.
    _a = a.split(' ');

    keys.forEach(function(k, i) {
        _a.forEach(function(b, j){
            if( b == k ) {
                score += 10;
                if(i == j) {
                    score += 3;
                }
                else {
                    score -= 1;
                }
            }
            else if(b.indexOf(k) > -1) {
                score += 3;
                if(i == j) {
                    score += 2;
                }
            }
            else {
                score -= 1;//Math.abs(b.length - k.length);
            }
        });
    });

    var diff = Math.abs(_a.length - keys.length);
    score -= diff;

    return score;
}

app.get('/companies', function(req, res) {
    var q = req.query.q;
    var s = req.query.s || 0;

    if(q.length < 1) {
        return res.send({error: 'Too few characters in query.'});
    }

    var _q = q.toLowerCase();
    var _keys = _q.split(' ');
    
    var r = companies.filter(function(c) {
        for(var i = 0; i < _keys.length; i++) {
            if (_keys[i].length > 2 && c.n.toLowerCase().indexOf(_keys[i]) > -1) {                
                return true;
            }            
        }
        return false;  
    });


    if(s === 1) {
        r = r.map(function(c) {
            return c.n;
        });
    }

    r.sort(function(a,b) {
        var sa = score(a.n, _keys);
        var sb = score(b.n, _keys);

        if(sa > sb) {
            return -1;
        }
        else if(sa < sb) {
            return 1;
        }
        return 0;
    });

    res.send(r);
});

console.log('Loading companies...');
var server, companies;
fs.readFile('data/companies.json', function(err, data) {
    if(err) throw err;
    companies = JSON.parse(data);
    server = app.listen(3000, function () {
        var port = server.address().port;
        console.log('Listening at port', port);
    });
});