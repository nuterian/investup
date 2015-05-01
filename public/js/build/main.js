var CompanyRow = React.createClass({displayName: "CompanyRow",
    render: function() {
        return (
                React.createElement("li", {className: "company-list-item row"}, 
                	React.createElement("div", {className: "company-item-img col"}, React.createElement("span", {className: "company-item-img-hlp"}), React.createElement("img", {src: this.props.company.i})), 
                	React.createElement("div", {className: "company-name col"}, React.createElement("a", {href: '#' + this.props.company.p}, this.props.company.n))
                )
        );
    }
});

var CompanyList = React.createClass({displayName: "CompanyList",
    render: function() {
        var rows = [],
        	to = Math.min(this.props.companies.length, 30);
        for( var i = 0; i < to; i++) {
        	var company = this.props.companies[i];
        	rows.push(React.createElement(CompanyRow, {company: company}));
        }
        return (
        	React.createElement("ul", {className: "company-list"}, 
        		rows
        	)
        );
    }
});

var SearchBar = React.createClass({displayName: "SearchBar",
	handleKeyDown: function() {
		var query = React.findDOMNode(this.refs.search).value.trim();
		this.props.onQuery(query);
	},

    componentWillMount: function() {
    	this.handleKeyDown = _.debounce(this.handleKeyDown, 200);
    },

    render: function() {
        return (
            React.createElement("input", {type: "text", placeholder: "Search by company name...", className: "sb", onKeyDown: this.handleKeyDown, ref: "search"})
        );
    }
});


var FilterableCompanyList = React.createClass({displayName: "FilterableCompanyList",
	getInitialState: function() {
		return {
			companies: []
		}
	},

	loadCompaniesFromServer: function(q) {
		var queryUrl =  this.props.url + q;
	    $.ajax({
	      	url: queryUrl,
	      	dataType: 'json',
	      	success: function(data) {
	        	this.setState({companies: data});
	      	}.bind(this),
	      	error: function(xhr, status, err) {
	        	console.error(queryUrl, status, err.toString());
	      	}.bind(this)
	    });		
	},

	handleOnQuery: function(q) {
		if(q.length < 2) {
			this.setState({companies: []});
		}
		else {
			this.loadCompaniesFromServer(q);
		}
	},

    render: function() {
        return (
        	React.createElement("div", null, 
	            React.createElement("div", {className: "header row"}, 
	            	React.createElement("h1", {className: "logo col"}, "Investup"), 
	                React.createElement(SearchBar, {
	                	className: "col", 
	                	onQuery: this.handleOnQuery}
	                )
	            ), 
	            React.createElement("div", {className: "list-wrapper"}, 
		            React.createElement(CompanyList, {
		            	companies: this.state.companies}
		            )
		        )
	        )
            
        );
    }
});

React.render(React.createElement(FilterableCompanyList, {url: "/companies?q="}), document.body);