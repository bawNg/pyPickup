$(document).ready(function(){
    function debug(object) { $('#debug').show('slow'); $('#debug').append(object + "<br />"); }
    colour_map = {0: 'white', 1: 'black', 2: 'blue', 3: 'green', 4: 'red', 5: 'brown', 
                  6: 'purple', 7: 'orange', 8: 'yellow', 9: 'lightgreen', 10: 'cyan',
                  11: 'lightcyan', 12: 'lightblue', 13: 'pink', 14: 'grey', 15: 'lightgrey'};
    
    $.fn.autoGrowInput = function(o) {
        o = $.extend({
            maxWidth: 650,
            minWidth: 100,
            comfortZone: 40
        }, o);

        this.filter('input:text').each(function(){
            var minWidth = o.minWidth || $(this).width(),
            val = '',
            input = $(this),
            testSubject = $('<tester/>').css({
                position: 'absolute',
                top: -9999,
                left: -9999,
                width: 'auto',
                fontSize: input.css('fontSize'),
                fontFamily: input.css('fontFamily'),
                fontWeight: input.css('fontWeight'),
                letterSpacing: input.css('letterSpacing'),
                whiteSpace: 'nowrap'
            }),
            check = function() {
                if (val === (val = input.val())) {return;}

                // Enter new content into testSubject
                var escaped = val.replace(/&/g, '&amp;').replace(/\s/g,'&nbsp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                testSubject.html(escaped);

                // Calculate new width + whether to change
                var testerWidth = testSubject.width(),
                    newWidth = (testerWidth + o.comfortZone) >= minWidth ? testerWidth + o.comfortZone : minWidth,
                    currentWidth = input.width(),
                    isValidWidthChange = (newWidth < currentWidth && newWidth >= minWidth)
                                         || (newWidth > minWidth && newWidth < o.maxWidth);

                // Animate width
                if (isValidWidthChange) {
                    input.width(newWidth);
                }
            };

            testSubject.insertAfter(input);
            $(this).bind('keyup keydown blur update', check);
            check();
        });
        return this;
    };
    
    $.editable.addInputType('growfield', {
        element : function(settings, original) {
            var input = $('<input />');
            if (settings.width  != 'none') { input.width(settings.width);  }
            if (settings.height != 'none') { input.height(settings.height); }
            input.attr('autocomplete','off');
            $(this).append(input);
            return(input);
        },
        plugin : function(settings, original) {
            // applies the growfield effect to the in-place edit field
            $('input', this).autoGrowInput();
        }
    });
    
    $.fn.make_editable = function() {
        $(this).editable(function(value, settings) {
            id = $(this).attr('id').substr(6).split('_');
            $.editable_values[id[0]][id[1]] = value;
            var category = $(this).parent().parent().prevAll('.span-24:first').text().toLowerCase();
            var name = $(this).parent().prevAll('.span-4:first').text();
            var post_data = { 'category': category, 'name': name, 'values[]': $.editable_values[id[0]] };
            
            $.post("/update", post_data, function(data){
                $.editable_values[id[0]] = data;
            }, "json");
            return value;
        }, {
            type      : 'growfield',
            indicator : '<img src="indicator.gif"> Saving...',
            tooltip   : 'Click to edit...',
            cancel    : 'Cancel',
            submit    : 'OK',
            style     : 'display: inline',
            data      : function(value, settings) {
                id = $(this).attr('id').substr(6).split('_')
                return $.editable_values[parseInt(id[0])][parseInt(id[1])];
            },
            onblur    : function(value, settings) {
                if (value == "") {
                    id = $(this).attr('id').substr(6).split('_');
                    $.editable_values[parseInt(id[0])].splice(parseInt(id[1]),1);
                    $(this).parent().prev().remove();
                    $(this).parent().remove();
                } else {
                    self = this;
                    $(this).t = setTimeout(function() { self.reset(); }, 500);
                }
            },
            callback : function(value, settings) {
                $(this).html(value);
                markup_to_html(this);
            }
        });
    };
    
    $.fn.repeat = function(times, string) { 
        this.each(function(){  
            var buff = string;  
            for(var i=1; i < times; i++){  
                buff += string;  
            }  
            $(this).append(buff);  
        });  
        return this;  
    }  
    
    $('.editable').make_editable();
    
    function markup_to_html(el) {
        with ($(el)) {
            id = attr('id').substr(6).split('_')
            if (!$.editable_values[parseInt(id[0])]) { $.editable_values[parseInt(id[0])] = []; }
            $.editable_values[parseInt(id[0])][parseInt(id[1])] = text();
            html(html().replace(/#B(.*?)#[BO]/g, "<strong>$1<\/strong>"));
            html(html().replace(/#U(.*?)#[UO]/g, "<u>$1</u>"));
            //$('.editable').html(replace(/#R(.*?)#R/, "<u>$1</u>"));
            html((html()+"#O").replace(/#C(\d+)(,(\d+))?([\s\S]*?)(?=#[CO])/g, function(str, p1, p2, p3, p4) {
                return "<span style='color: " + colour_map[parseInt(p1)] + "'>" + p4 + "</span>"
            }));
            html(html().replace(/#O/g, ""));
            after('<span class="text-button-container">&nbsp;<span class="text-button-add">[+]</span></span>');
        }
    }
    
    $.editable_values = {};
    $('.editable').each(function(i, el) {
        markup_to_html(el);
    });
    $(".text-button-container").hover(function(e) {
        $(this).children().show()
    }, function() {
        $(this).children().hide()
    });
    $('.text-button-add').click(function(){
        with ($(this).parent()) {
            prev_id = prev('.editable').attr('id').substr(6).split('_');
            output = '<div class="span-4">&nbsp;</div><div class="span-20 last">';
            id = 'value_' + prev_id[0] + '_' + (parseInt(prev_id[1])+1)
            output += '<span id="'+id+'" class="editable value_'+prev_id[0]+'"></span>';
            parent().after(output + '<span class="text-button-container">&nbsp;<span class="text-button-add">[+]</span></span></div>');
            $('#'+id).repeat(prev('.editable').text().length*1.25, '&nbsp;')
            $('#'+id).make_editable();
            $.editable_values[parseInt(prev_id[0])].splice(parseInt(prev_id[1])+1,0,"");
            $('#'+id).click();
        }
        var id = 0
        $('.value_' + prev_id[0]).each(function(el) {
            $(el).attr("id", 'value_' + prev_id[0] + '_' + id);
            id++;
        });
        
        
    });
    //slides the element with class "menu_body" when paragraph with class "menu_head" is clicked
    $("#container div.menu_head").click(function()
    {
        $(this).next("div.menu_body").slideToggle(400).siblings("div.menu_body").slideUp("slow");
    });
});
