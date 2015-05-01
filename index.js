var express = require('express');
var app = express();
var fs = require('fs');

app.use(express.static('public'));
app.set('views', './views');
app.set('view engine', 'jade');

app.get('/', function (req, res) {
    res.render('index');
});

app.get('/companies', function(req, res) {
    var q = req.query.q;
    var s = req.query.s || 0;

    if(q.length < 1) {
        return res.send({error: 'Too few characters in query.'});
    }

    var _q = q.toLowerCase();
    var r = companies.filter(function(c) {
        return c.n.toLowerCase().indexOf(_q) > -1;
    });

    if(s === 1) {
        r = r.map(function(c) {
            return c.n;
        });
    }

    r.sort(function(a,b) {
        var _a = a.n.toLowerCase();
        var _b = b.n.toLowerCase();

        if(_a === _q) {
            return -1;
        }

        if(_b === _q) {
            return 1;
        }

        var aIndex = _a.indexOf(_q);
        var bIndex = _b.indexOf(_q);

        if(aIndex < bIndex) {
            return -1;
        }
        else if(aIndex > bIndex) {
            return 1;
        }

        var re = new RegExp('\\b' + _q + '\\b', 'i');
        if(re.test(_a)) {
            return -1;
        }

        if(re.test(_b)) {
            return 1;
        }

        var adiff = Math.abs(q.length - _a.length);
        var bdiff = Math.abs(q.length - _b.length);

        if(adiff < bdiff) {
            return -1;
        }
        else if(adiff > bdiff) {
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