(function(define, undefined) {
    'use strict';
    define([
        'gettext', 'jquery', 'underscore', 'backbone', 'logger',
        'js/student_account/models/user_account_model',
        'js/student_account/models/user_preferences_model',
        'js/student_account/views/account_settings_fields',
        'js/student_account/views/account_settings_view',
        'edx-ui-toolkit/js/utils/string-utils',
        'edx-ui-toolkit/js/utils/html-utils'
    ], function(gettext, $, _, Backbone, Logger, UserAccountModel, UserPreferencesModel,
                 AccountSettingsFieldViews, AccountSettingsView, StringUtils, HtmlUtils) {
        return function(
            fieldsData,
            ordersHistoryData,
            authData,
            passwordResetSupportUrl,
            userAccountsApiUrl,
            userPreferencesApiUrl,
            accountUserId,
            platformName,
            contactEmail,
            allowEmailChange
        ) {
            var accountSettingsElement, userAccountModel, userPreferencesModel, aboutSectionsData,
                accountsSectionData, ordersSectionData, accountSettingsView, showAccountSettingsPage,
                showLoadingError, orderNumber, getUserField, userFields, additionalFields, timeZoneDropdownField, countryDropdownField;

            accountSettingsElement = $('.wrapper-account-settings');

            userAccountModel = new UserAccountModel();
            userAccountModel.url = userAccountsApiUrl;

            userPreferencesModel = new UserPreferencesModel();
            userPreferencesModel.url = userPreferencesApiUrl;

			var keep_profile = HtmlUtils.joinHtml(
				HtmlUtils.interpolateHtml(
					HtmlUtils.HTML('<a href="{settings_url}">'), {settings_url: "https://account.keep.edu.hk/account/profile"}
				),
				gettext('KEEP Profile'),
				HtmlUtils.HTML('</a>')
			);
			
            aboutSectionsData = [
                {
                    title: gettext('Basic Account Information'),
                    subtitle: HtmlUtils.interpolateHtml(
                        gettext('These settings include information about your account. You can update your basic information at {keep_profile}'),  // eslint-disable-line max-len
                        {'keep_profile': keep_profile}
                    ),
                    fields: [
                        {
                            view: new AccountSettingsFieldViews.ReadonlyFieldView({
                                model: userAccountModel,
                                title: gettext('Username'),
                                valueAttribute: 'username',
                                helpMessage: StringUtils.interpolate(
                                    gettext('The name that identifies you throughout {platform_name}. You cannot change your username.'),  // eslint-disable-line max-len
                                    {platform_name: platformName}
                                )
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.ReadonlyFieldView({
                                model: userAccountModel,
                                title: gettext('Full Name'),
                                valueAttribute: 'name',
                                helpMessage: gettext(
                                    'The name that will appear on your certificates. Other learners never see your full name. To change this, edit your KEEP Profile.'  // eslint-disable-line max-len
                                )
                            })
                        },
                        {
							view: new AccountSettingsFieldViews.ReadonlyFieldView({
								model: userAccountModel,
								title: gettext('Email Address'),
								valueAttribute: 'email',
								helpMessage: StringUtils.interpolate(
									gettext('The email address you use to sign in. Communications from {platform_name} and your courses are sent to this address.'),  // eslint-disable-line max-len
									{platform_name: platformName}
								)
							})
						},
					    {
                            view: new AccountSettingsFieldViews.PasswordFieldView({
                                model: userAccountModel,
                                title: gettext('Password'),
                                screenReaderTitle: gettext('Reset your password'),
                                valueAttribute: 'password',
                                emailAttribute: 'email',
                                passwordResetSupportUrl: passwordResetSupportUrl,
                                linkTitle: gettext('Reset your password'),
                                linkHref: 'https://account.keep.edu.hk/account/recovery',
                                helpMessage: StringUtils.interpolate(
                                    gettext('When you select "Reset your password", you will be sent to the KEEP Account Recovery page.'),  // eslint-disable-line max-len
                                    {platform_name: platformName}
                                )
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.DropdownFieldView({
                                model: userAccountModel,
                                required: true,
                                title: gettext('Country or Region'),
                                valueAttribute: 'country',
                                options: fieldsData.country.options,
				editable: 'never',
				placeholderValue: '--'
                            })
                        },
						{
                            view: new AccountSettingsFieldViews.DropdownFieldView({
                                model: userAccountModel,
                                title: gettext('Gender'),
                                valueAttribute: 'gender',
                                options: fieldsData.gender.options,
                                editable: 'never',
                                placeholderValue: '--'
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.DropdownFieldView({
                                model: userAccountModel,
                                title: gettext('Year of Birth'),
                                valueAttribute: 'year_of_birth',
                                options: fieldsData.year_of_birth.options,
                                editable: 'never',
                                placeholderValue: '--'
                            })
                        } 
                    ]
                },
                {
                    title: gettext('Additional Information'),
                    fields: [
                        {
                            view: new AccountSettingsFieldViews.LanguagePreferenceFieldView({
                                model: userPreferencesModel,
                                title: gettext('Site Language'),
                                valueAttribute: 'pref-lang',
                                required: true,
                                refreshPageOnSave: true,
                                helpMessage: StringUtils.interpolate(
                                    gettext('The language used throughout this site. This site is currently available in a limited number of languages.'),  // eslint-disable-line max-len
                                    {platform_name: platformName}
                                ),
                                options: fieldsData.language.options,
                                persistChanges: true
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.LanguageProficienciesFieldView({
                                model: userAccountModel,
                                title: gettext('Preferred Language'),
                                valueAttribute: 'language_proficiencies',
								helpMessage: StringUtils.interpolate(
                                    gettext('This will be visible to other users if you choose to show your Full profile'),  // eslint-disable-line max-len
                                    {platform_name: platformName}
                                ),
                                options: fieldsData.preferred_language.options,
                                persistChanges: true
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.TimeZoneFieldView({
                                model: userPreferencesModel,
                                required: true,
                                title: gettext('Time Zone'),
                                valueAttribute: 'time_zone',
                                helpMessage: gettext('Select the time zone for displaying course dates. If you do not specify a time zone, course dates, including assignment deadlines, will be displayed in your browser\'s local time zone.'), // eslint-disable-line max-len
                                groupOptions: [{
                                    groupTitle: gettext('All Time Zones'),
                                    selectOptions: fieldsData.time_zone.options,
                                    nullValueOptionLabel: gettext('Default (Local Time Zone)')
                                }],
                                persistChanges: true
                            })
                        },
						{
                            view: new AccountSettingsFieldViews.DropdownFieldView({
                                model: userAccountModel,
                                title: gettext('Education Completed'),
                                valueAttribute: 'level_of_education',
                                options: fieldsData.level_of_education.options,
                                persistChanges: true
                            })
                        }
                    ]
                }
            ];

            // set TimeZoneField to listen to CountryField
            getUserField = function(list, search) {
                return _.find(list, function(field) {
                    return field.view.options.valueAttribute === search;
                }).view;
            };
            userFields = _.find(aboutSectionsData, function(section) {
                return section.title === gettext('Basic Account Information');
            }).fields;
			additionalFields = _.find(aboutSectionsData, function(section) {
                return section.title === gettext('Additional Information');
            }).fields;
            timeZoneDropdownField = getUserField(additionalFields, 'time_zone');
            countryDropdownField = getUserField(userFields, 'country');
            timeZoneDropdownField.listenToCountryView(countryDropdownField);

            accountsSectionData = [
                {
                    title: gettext('Linked Accounts'),
                    subtitle: StringUtils.interpolate(
                        gettext('You can link your social media accounts to simplify signing in to {platform_name}.'),
                        {platform_name: platformName}
                    ),
                    fields: _.map(authData.providers, function(provider) {
                        return {
                            view: new AccountSettingsFieldViews.AuthFieldView({
                                title: provider.name,
                                valueAttribute: 'auth-' + provider.id,
                                helpMessage: '',
                                connected: provider.connected,
                                connectUrl: provider.connect_url,
                                acceptsLogins: provider.accepts_logins,
                                disconnectUrl: provider.disconnect_url,
                                platformName: platformName
                            })
                        };
                    })
                }
            ];

            ordersHistoryData.unshift(
                {
                    title: gettext('ORDER NAME'),
                    order_date: gettext('ORDER PLACED'),
                    price: gettext('TOTAL'),
                    number: gettext('ORDER NUMBER')
                }
            );

            ordersSectionData = [
                {
                    title: gettext('My Orders'),
                    subtitle: StringUtils.interpolate(
                        gettext('This page contains information about orders that you have placed with {platform_name}.'),  // eslint-disable-line max-len
                        {platform_name: platformName}
                    ),
                    fields: _.map(ordersHistoryData, function(order) {
                        orderNumber = order.number;
                        if (orderNumber === 'ORDER NUMBER') {
                            orderNumber = 'orderId';
                        }
                        return {
                            view: new AccountSettingsFieldViews.OrderHistoryFieldView({
                                totalPrice: order.price,
                                orderId: order.number,
                                orderDate: order.order_date,
                                receiptUrl: order.receipt_url,
                                valueAttribute: 'order-' + orderNumber,
                                lines: order.lines
                            })
                        };
                    })
                }
            ];

            accountSettingsView = new AccountSettingsView({
                model: userAccountModel,
                accountUserId: accountUserId,
                el: accountSettingsElement,
                tabSections: {
                    aboutTabSections: aboutSectionsData,
                    accountsTabSections: accountsSectionData,
                    ordersTabSections: ordersSectionData
                },
                userPreferencesModel: userPreferencesModel
            });

            accountSettingsView.render();

            showAccountSettingsPage = function() {
                // Record that the account settings page was viewed.
                Logger.log('edx.user.settings.viewed', {
                    page: 'account',
                    visibility: null,
                    user_id: accountUserId
                });
            };

            showLoadingError = function() {
                accountSettingsView.showLoadingError();
            };

            userAccountModel.fetch({
                success: function() {
                    // Fetch the user preferences model
                    userPreferencesModel.fetch({
                        success: showAccountSettingsPage,
                        error: showLoadingError
                    });
                },
                error: showLoadingError
            });

            return {
                userAccountModel: userAccountModel,
                userPreferencesModel: userPreferencesModel,
                accountSettingsView: accountSettingsView
            };
        };
    });
}).call(this, define || RequireJS.define);
