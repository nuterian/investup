function numberWithCommas(x) {
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

var CompanyThumbnail = React.createClass({displayName: "CompanyThumbnail",
	getInitialState: function() {
		return {
			status: 'loading'
		}
	},

	componentWillMount: function(){
		if(!this.props.src) {
			this.handleError();
		}
	},

	componentWillReceiveProps: function(nextProps) {
		if(nextProps.src !== this.props.src) {
			var imgNode = this.refs.img.getDOMNode();
			imgNode.style.width = this.props.maxSize + 'px';
			imgNode.style.height = this.props.maxSize + 'px';
			imgNode.style.marginTop = null;
			imgNode.style.marginLeft = null;
			this.setState({
				status: 'loading'
			});			
		}
	},	

	handleLoad: function(){
		var imgNode = this.refs.img.getDOMNode();
		if(imgNode.width > imgNode.height) {
			imgNode.style.width = this.props.maxSize + 'px';
			imgNode.style.height = 'auto';
			imgNode.style.marginTop = (this.props.maxSize / 2 - (this.props.maxSize * imgNode.height / imgNode.width) / 2) + 'px';
		}
		else {
			imgNode.style.height = this.props.maxSize + 'px';
			imgNode.style.width = 'auto';
			imgNode.style.marginLeft = (this.props.maxSize / 2 - (this.props.maxSize * imgNode.width / imgNode.height) / 2) + 'px';
		}
		this.setState({
			status: 'loaded'
		});
	},

	handleError: function(){
		this.setState({
			status: 'failed'
		});
	},

	render: function() {
	    var className = 'thumb-' + this.state.status;
	    return (
	    	React.createElement("div", {className: className}, 
		    	React.createElement("div", {className: "spinner"}), 
		      	React.createElement("img", {src: this.props.src, alt: this.props.alt, onLoad: this.handleLoad, onError: this.handleError, ref: "img"})
		     )
	    );
	}
});

var CompanyRow = React.createClass({displayName: "CompanyRow",
    render: function() {
    	var maxThumbSize = 40;
        return (
                React.createElement("li", {className: "company-list-item row"}, 
                	React.createElement("div", {className: "company-item-img col"}, 
                		React.createElement(CompanyThumbnail, {src: this.props.company.i, maxSize: maxThumbSize})
                	), 
                	React.createElement("div", {className: "company-name col"}, React.createElement("a", {href: '#' + this.props.company.p}, this.props.company.n))
                )
        );
    }
});

function pager(page) {
	if(page.numPages < 2) 
		return;

	var pageLinks = [];
	if (page.currentPage > 1) {
		pageLinks.push(React.createElement("a", {className: "page-link col", onClick: page.handleClick(page.currentPage - 1)}, "‹"))
	}

	var startPage = page.currentPage - (page.currentPage > 1 ? 6 : 7);
	var endPage = page.currentPage + 6;
	if (startPage <= 0) {
	    endPage -= (startPage - 1);
	    startPage = 1;
	}
	if (endPage > page.numPages) {
    	endPage = page.numPages;
	}

	for(var i = startPage; i <= endPage; i++) {
		if(page.currentPage == i) {
			pageLinks.push(React.createElement("a", {className: "page-link page-curr col"}, i))	
		}
		else {
			pageLinks.push(React.createElement("a", {className: "page-link col", onClick: page.handleClick(i)}, i))
		}		
	}

	if (page.currentPage < page.numPages) {
		pageLinks.push(React.createElement("span", {className: "page-link col-right", onClick: page.handleClick(page.currentPage + 1)}, "›"))
	}
	return React.createElement("div", {className: "pager row"}, pageLinks)
}

var CompanyList = React.createClass({displayName: "CompanyList",
	getInitialState: function() {
		return {
			currentPage: 1
		}
	},

	getDefaultProps: function() {
		return {
			pageSize: 10
		}
	},
	
	componentWillReceiveProps: function(nextProps) {
    	this.setState({
      		currentPage: 1
    	})
  	},

	getPage: function() {
	   	var start = this.props.pageSize * (this.state.currentPage - 1);
	    var end = start + this.props.pageSize;

	    return {
	      	currentPage: this.state.currentPage, 
	      	companies: this.props.companies.slice(start, end), 
	      	numPages: this.getNumPages(), 
	      	handleClick: function(pageNum) {
	        	return function() { 
	        		this.handlePageChange(pageNum);
	        	}.bind(this)
	      	}.bind(this)
	    }
	},

	getNumPages: function() {
	    var numPages = Math.floor(this.props.companies.length / this.props.pageSize);
	    if (this.props.companies.length % this.props.pageSize > 0) {
	      	numPages++
	    }
	    return numPages;
	},

	handlePageChange: function(pageNum) {
	    this.setState({currentPage: pageNum});
	},

    render: function() {
    	var page = this.getPage();
        var rows = page.companies.map(function(company) {
        	return React.createElement(CompanyRow, {company: company})
        });
        return (
        	React.createElement("div", null, 
        		React.createElement("div", {className: "result-status"}, this.props.companies.length > 0 ? numberWithCommas(this.props.companies.length) + ' results' : this.props.query === '' ? 'Type a query' : 'Your query \'' + this.props.query + '\' returned no results'), 
	        	React.createElement("ul", {className: "company-list"}, 
	        		rows
	        	), 
	        	pager(page)
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
    	this.handleKeyDown = _.debounce(this.handleKeyDown, 300);
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
			companies: [],
			query: ''
		}
	},

	loadCompaniesFromServer: function(q) {
		var queryUrl =  this.props.url + q;
	    $.ajax({
	      	url: queryUrl,
	      	dataType: 'json',
	      	success: function(data) {
	        	this.setState({companies: data, query: q});
	      	}.bind(this),
	      	error: function(xhr, status, err) {
	        	console.error(queryUrl, status, err.toString());
	      	}.bind(this)
	    });		
	},

	handleOnQuery: function(q) {
		if(q.length < 3) {
			this.setState({companies: [], query: ''});
		}
		else {
			this.loadCompaniesFromServer(q);
		}
	},

    render: function() {
        return (
        	React.createElement("div", null, 
	            React.createElement("div", {className: "header row"}, 
	            	React.createElement("div", {className: "wrapper"}, 
		            	React.createElement("h1", {className: "logo col"}, "Investup"), 
		                React.createElement(SearchBar, {
		                	className: "col", 
		                	onQuery: this.handleOnQuery}
		                )
		            )
	            ), 
	           	React.createElement("div", {className: "wrapper"}, 
		            React.createElement("div", {className: "list-wrapper"}, 
			            React.createElement(CompanyList, {
			            	companies: this.state.companies, 
			            	query: this.state.query}
			            )
			        )
			    )
	        )
            
        );
    }
});

React.render(React.createElement(FilterableCompanyList, {url: "/companies?q="}), document.body);