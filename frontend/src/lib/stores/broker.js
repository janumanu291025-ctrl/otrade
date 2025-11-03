import { writable, derived } from 'svelte/store';
import { brokerAPI } from '../utils/api';

function createBrokerStore() {
    const { subscribe, set, update } = writable({
        brokerType: 'kite',
        configured: false,
        connected: false,
        tokenExpired: false,
        profile: null,
        funds: null,
        loading: false,
        error: null
    });

    return {
        subscribe,
        
        setBrokerType(type) {
            update(state => ({ ...state, brokerType: type }));
        },

        async loadStatus(brokerType) {
            update(state => ({ ...state, loading: true, error: null }));
            try {
                const response = await brokerAPI.getStatus(brokerType);
                update(state => ({
                    ...state,
                    brokerType,
                    configured: response.data.configured,
                    connected: response.data.connected,
                    tokenExpired: response.data.token_expired || false,
                    loading: false
                }));
            } catch (error) {
                update(state => ({ 
                    ...state, 
                    error: error.message,
                    loading: false 
                }));
            }
        },

        async loadProfile(brokerType) {
            try {
                const response = await brokerAPI.getProfile(brokerType);
                update(state => ({ ...state, profile: response.data }));
            } catch (error) {
                console.error('Failed to load profile:', error);
            }
        },

        async loadFunds(brokerType) {
            try {
                const response = await brokerAPI.getFunds(brokerType);
                update(state => ({ ...state, funds: response.data }));
            } catch (error) {
                console.error('Failed to load funds:', error);
            }
        },

        async disconnect(brokerType) {
            try {
                await brokerAPI.disconnect(brokerType);
                update(state => ({
                    ...state,
                    connected: false,
                    profile: null,
                    funds: null
                }));
            } catch (error) {
                update(state => ({ ...state, error: error.message }));
            }
        }
    };
}

export const broker = createBrokerStore();
